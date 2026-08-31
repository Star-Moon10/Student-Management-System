"""Restore a controlled update that was interrupted before its health check completed."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


RUNTIME_DIRECTORIES = ("app", "scripts", "docs")
RUNTIME_FILES = (
    ".env.example",
    "Dockerfile",
    "LICENSE",
    "README.md",
    "VERSION",
    "docker-compose.yml",
    "pyproject.toml",
    "requirements.lock",
    "setup.bat",
    "start-system.bat",
    "stop-system.bat",
)
INCOMPLETE_STATES = {"prepared", "applying", "installing", "restarting", "rolling_back"}


class RecoveryError(RuntimeError):
    pass


def _project_child(project_root: Path, value: str | Path) -> Path:
    root = project_root.resolve()
    candidate = Path(value).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise RecoveryError(f"Recovery path is outside the project: {candidate}") from exc
    return candidate


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _write_status(project_root: Path, payload: dict[str, Any]) -> None:
    payload["updated_at"] = datetime.now().astimezone().isoformat()
    _write_json(project_root / "run" / "update-status.json", payload)


def _restore_directory(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    if source.is_dir():
        shutil.copytree(source, target)


def recover_interrupted_update(project_root: Path) -> dict[str, Any]:
    root = project_root.resolve()
    transaction_path = root / "run" / "update-transaction.json"
    if not transaction_path.is_file():
        return {"recovered": False, "reason": "no_transaction"}
    try:
        transaction = json.loads(transaction_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecoveryError("The interrupted-update transaction marker is unreadable") from exc
    if not isinstance(transaction, dict) or int(transaction.get("format", 0)) != 1:
        raise RecoveryError("The interrupted-update transaction marker is invalid")
    if str(transaction.get("state") or "") not in INCOMPLETE_STATES:
        transaction_path.unlink(missing_ok=True)
        return {"recovered": False, "reason": "transaction_already_final"}

    rollback_directory = _project_child(root, str(transaction.get("rollback_directory") or ""))
    if not rollback_directory.is_dir():
        raise RecoveryError("The update rollback directory is missing")

    for directory in RUNTIME_DIRECTORIES:
        _restore_directory(rollback_directory / directory, _project_child(root, root / directory))
    for file_name in RUNTIME_FILES:
        source = rollback_directory / file_name
        target = _project_child(root, root / file_name)
        if source.is_file():
            shutil.copy2(source, target)

    database_restored = False
    database_rollback = transaction.get("database_rollback_path")
    database_path = transaction.get("database_path")
    if database_rollback and database_path:
        source = _project_child(root, str(database_rollback))
        target = _project_child(root, str(database_path))
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            database_restored = True

    transaction_path.unlink(missing_ok=True)
    _write_status(
        root,
        {
            "state": "rolled_back",
            "message": "检测到未完成更新，已自动恢复更新前版本。",
            "progress": 100,
            "error": "",
            "job_id": transaction.get("job_id"),
            "recovered_on_startup": True,
            "database_restored": database_restored,
        },
    )
    return {"recovered": True, "database_restored": database_restored, "job_id": transaction.get("job_id")}


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover a controlled update interrupted before completion.")
    parser.add_argument("--project-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = recover_interrupted_update(args.project_root)
    except RecoveryError as exc:
        print(f"Update recovery failed: {exc}", file=sys.stderr)
        return 1
    if result["recovered"]:
        print("Recovered the interrupted update before starting the service.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
