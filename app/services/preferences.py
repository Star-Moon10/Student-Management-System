from typing import Any

from sqlalchemy.orm import Session

from app.models import SystemPreference, User


DEFAULT_CONTROLS = {
    "ai_operations_enabled": True,
    "ai_export_confirmation_required": True,
}


def get_controls(db: Session) -> dict[str, bool]:
    row = db.get(SystemPreference, "security_controls")
    values = row.value if row and isinstance(row.value, dict) else {}
    return {key: bool(values.get(key, default)) for key, default in DEFAULT_CONTROLS.items()}


def set_controls(db: Session, values: dict[str, Any], actor: User) -> dict[str, bool]:
    controls = {key: bool(values.get(key, default)) for key, default in DEFAULT_CONTROLS.items()}
    row = db.get(SystemPreference, "security_controls")
    if row is None:
        row = SystemPreference(key="security_controls", value=controls, updated_by_id=actor.id)
        db.add(row)
    else:
        row.value = controls
        row.updated_by_id = actor.id
    db.flush()
    return controls
