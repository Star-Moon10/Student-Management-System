from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Lock
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import SessionLocal
from app.models import BackgroundTask, User, utcnow


_executor = ThreadPoolExecutor(max_workers=max(1, get_settings().task_workers), thread_name_prefix="sms-task")
_submit_lock = Lock()


def serialize_task(task: BackgroundTask) -> dict[str, Any]:
    return {"id": task.id, "task_type": task.task_type, "status": task.status, "progress": task.progress, "message": task.message, "result": task.result or {}, "error_message": task.error_message, "created_by_id": task.created_by_id, "created_at": task.created_at, "started_at": task.started_at, "completed_at": task.completed_at}


def update_task(db: Session, task_id: str, progress: int, message: str | None = None, result: dict[str, Any] | None = None) -> None:
    task = db.get(BackgroundTask, task_id)
    if not task:
        return
    task.progress = max(0, min(100, progress))
    if message is not None:
        task.message = message[:255]
    if result is not None:
        task.result = result
    db.commit()


def submit_task(db: Session, task_type: str, actor: User | None, worker: Callable[[str, Session], dict[str, Any]]) -> BackgroundTask:
    task = BackgroundTask(id=str(uuid4()), task_type=task_type, status="queued", progress=0, message="等待执行", created_by_id=actor.id if actor else None)
    db.add(task)
    db.flush()
    task_id = task.id

    def run() -> None:
        worker_db = SessionLocal()
        try:
            record = worker_db.get(BackgroundTask, task_id)
            if not record:
                return
            record.status = "running"
            record.progress = 5
            record.message = "正在执行"
            record.started_at = utcnow()
            worker_db.commit()
            result = worker(task_id, worker_db)
            record = worker_db.get(BackgroundTask, task_id)
            if record:
                record.status = "completed"
                record.progress = 100
                record.message = "已完成"
                record.result = result or {}
                record.completed_at = utcnow()
                worker_db.commit()
        except Exception as exc:
            worker_db.rollback()
            record = worker_db.get(BackgroundTask, task_id)
            if record:
                record.status = "failed"
                record.error_message = str(exc)[:2000]
                record.message = "执行失败"
                record.completed_at = utcnow()
                worker_db.commit()
        finally:
            worker_db.close()

    cutoff = utcnow() - timedelta(days=max(1, get_settings().task_retention_days))
    db.execute(delete(BackgroundTask).where(BackgroundTask.created_at < cutoff))
    db.commit()
    with _submit_lock:
        _executor.submit(run)
    return task
