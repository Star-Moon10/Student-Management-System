import hashlib
import hmac
import json
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_china_time
from app.models import AuditLog, User


def _entry_payload(entry: AuditLog, previous_hash: str | None) -> bytes:
    created_at = entry.created_at
    created_at = as_china_time(created_at)
    payload = {
        "id": entry.id,
        "actor_id": entry.actor_id,
        "action": entry.action,
        "entity_type": entry.entity_type,
        "entity_id": entry.entity_id,
        "before": entry.before_data,
        "after": entry.after_data,
        "ip": entry.ip_address,
        "created_at": created_at.isoformat() if created_at else "",
        "previous_hash": previous_hash or "",
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":")).encode("utf-8")


def _entry_hash(entry: AuditLog, previous_hash: str | None) -> str:
    return hmac.new(get_settings().jwt_secret.encode("utf-8"), _entry_payload(entry, previous_hash), hashlib.sha256).hexdigest()


def audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str | int,
    actor: User | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before_data=before,
        after_data=after,
        ip_address=request.client.host if request and request.client else None,
    )
    db.add(entry)
    db.flush()
    previous_hash = db.scalar(
        select(AuditLog.entry_hash)
        .where(AuditLog.id < entry.id, AuditLog.entry_hash.is_not(None))
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    entry.previous_hash = previous_hash
    entry.entry_hash = _entry_hash(entry, previous_hash)
    db.flush()
    return entry


def verify_audit_chain(db: Session) -> dict[str, Any]:
    entries = list(db.scalars(select(AuditLog).where(AuditLog.entry_hash.is_not(None)).order_by(AuditLog.id.asc())))
    previous_hash: str | None = None
    checked = 0
    for entry in entries:
        if entry.previous_hash != previous_hash or entry.entry_hash != _entry_hash(entry, previous_hash):
            return {"valid": False, "checked": checked, "failed_id": entry.id}
        previous_hash = entry.entry_hash
        checked += 1
    return {"valid": True, "checked": checked, "failed_id": None}
