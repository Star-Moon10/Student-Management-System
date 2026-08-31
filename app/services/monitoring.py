import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_china_time
from app.db import engine
from app.models import BackgroundTask, SystemAlert, SystemBackup, User, utcnow
from app.services.ai import get_ai_health


def _as_china_time(value: datetime | None) -> datetime | None:
    return as_china_time(value)


def system_snapshot(db: Session) -> dict[str, Any]:
    settings = get_settings()
    database_path = Path(engine.url.database) if engine.dialect.name == "sqlite" and engine.url.database else None
    disk_root = settings.storage_path.resolve().anchor or str(settings.storage_path.resolve())
    disk = shutil.disk_usage(disk_root)
    latest_backup = db.scalar(select(SystemBackup).order_by(SystemBackup.created_at.desc()).limit(1))
    failed_tasks = db.scalar(select(func.count()).select_from(BackgroundTask).where(BackgroundTask.status == "failed")) or 0
    return {
        "disk": {"total": disk.total, "used": disk.used, "free": disk.free},
        "database": {"dialect": engine.dialect.name, "size_bytes": database_path.stat().st_size if database_path and database_path.is_file() else 0},
        "ai": get_ai_health(),
        "latest_backup": latest_backup,
        "tasks": {"queued": db.scalar(select(func.count()).select_from(BackgroundTask).where(BackgroundTask.status == "queued")) or 0, "running": db.scalar(select(func.count()).select_from(BackgroundTask).where(BackgroundTask.status == "running")) or 0, "failed": failed_tasks},
    }


def _upsert_alert(db: Session, key: str, severity: str, title: str, detail: str, active: bool, actor: User | None) -> tuple[SystemAlert | None, bool]:
    alert = db.scalar(select(SystemAlert).where(SystemAlert.alert_key == key))
    if not active:
        if alert and alert.status != "resolved":
            alert.status = "resolved"
            alert.last_seen_at = utcnow()
        return alert, False
    is_new = alert is None or alert.status == "resolved"
    if alert is None:
        alert = SystemAlert(alert_key=key, severity=severity, title=title, detail=detail)
        db.add(alert)
    else:
        alert.severity = severity
        alert.title = title
        alert.detail = detail
        alert.status = "open"
        alert.last_seen_at = utcnow()
        if is_new:
            alert.first_seen_at = utcnow()
            alert.acknowledged_at = None
            alert.acknowledged_by_id = None
    return alert, is_new


def _notify_webhook(payload: dict[str, Any]) -> None:
    url = get_settings().notification_webhook_url
    if not url:
        return
    try:
        httpx.post(url, json=payload, timeout=5)
    except httpx.HTTPError:
        # A notification channel must never break the archive service.
        return


def evaluate_alerts(db: Session, actor: User | None = None) -> list[SystemAlert]:
    settings = get_settings()
    snapshot = system_snapshot(db)
    latest = snapshot["latest_backup"]
    offsite_failed = bool(settings.backup_offsite_path and latest and (latest.manifest or {}).get("offsite", {}).get("status") != "completed")
    latest_created_at = _as_china_time(latest.created_at) if latest else None
    backup_stale = not latest or not latest_created_at or latest_created_at < utcnow() - timedelta(days=2) or latest.validation_status == "failed" or offsite_failed
    checks = [
        ("disk_free", "high", "磁盘可用空间不足", f"当前可用空间 {snapshot['disk']['free'] / 1024 ** 3:.1f} GB，阈值为 {settings.alert_disk_free_gb} GB", snapshot["disk"]["free"] < settings.alert_disk_free_gb * 1024 ** 3),
        ("local_ai", "warning", "本地 AI 服务降级", str(snapshot["ai"].get("detail") or "本地 AI 不可用"), not bool(snapshot["ai"].get("available"))),
        ("backup", "high", "备份需要处理", "尚未建立有效的近期备份、最近一次校验失败，或异地副本复制失败", backup_stale),
        ("failed_tasks", "warning", "后台任务连续失败", f"失败任务数为 {snapshot['tasks']['failed']}，阈值为 {settings.alert_task_failure_threshold}", snapshot["tasks"]["failed"] >= settings.alert_task_failure_threshold),
    ]
    open_alerts: list[SystemAlert] = []
    for key, severity, title, detail, active in checks:
        alert, is_new = _upsert_alert(db, key, severity, title, detail, active, actor)
        if alert and active:
            open_alerts.append(alert)
            if is_new:
                _notify_webhook({"event": "student_system_alert", "severity": severity, "title": title, "detail": detail, "alert_key": key, "at": utcnow().isoformat()})
    db.flush()
    return open_alerts


def serialize_alert(alert: SystemAlert) -> dict[str, Any]:
    return {"id": alert.id, "key": alert.alert_key, "severity": alert.severity, "title": alert.title, "detail": alert.detail, "status": alert.status, "first_seen_at": alert.first_seen_at, "last_seen_at": alert.last_seen_at, "acknowledged_at": alert.acknowledged_at, "acknowledged_by_id": alert.acknowledged_by_id}
