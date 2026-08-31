"""Controlled GitHub Release updates for the Windows local deployment."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
try:
    import truststore
except ImportError:  # Allows source checks before the project dependencies are installed.
    truststore = None
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import china_now
from app.models import SystemPreference
from app.services.crypto import decrypt_text, encrypt_text
from app.version import APP_RELEASE


UPDATE_CONFIGURATION_KEY = "update_configuration"
UPDATE_STATUS_FILE = "update-status.json"
UPDATE_JOB_DIRECTORY = "updates"
UPDATE_PACKAGE_ASSET = "student-management-update.zip"
UPDATE_CHECKSUM_ASSET = "student-management-update.zip.sha256"
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def update_run_root() -> Path:
    target = project_root() / "run" / UPDATE_JOB_DIRECTORY
    target.mkdir(parents=True, exist_ok=True)
    return target


def update_status_path() -> Path:
    target = project_root() / "run" / UPDATE_STATUS_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def _safe_status_payload(payload: dict[str, Any]) -> dict[str, Any]:
    safe = {key: value for key, value in payload.items() if "token" not in key.lower()}
    return safe | {"updated_at": china_now().isoformat()}


def write_update_status(payload: dict[str, Any]) -> dict[str, Any]:
    target = update_status_path()
    temporary = target.with_suffix(".tmp")
    safe = _safe_status_payload(payload)
    temporary.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(target)
    return safe


def get_update_status() -> dict[str, Any]:
    target = update_status_path()
    if not target.is_file():
        return {"state": "idle", "updated_at": None}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
        return _safe_status_payload(payload if isinstance(payload, dict) else {"state": "unknown"})
    except (OSError, json.JSONDecodeError):
        return {"state": "unknown", "message": "无法读取更新状态文件", "updated_at": None}


def normalize_repository(value: str | None) -> str:
    repository = str(value or "").strip().strip("/")
    if repository.startswith("https://github.com/"):
        repository = repository.removeprefix("https://github.com/").removesuffix(".git").strip("/")
    if repository and not REPOSITORY_PATTERN.fullmatch(repository):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="GitHub 仓库格式应为 owner/repository")
    return repository


def _release_version(value: str | None) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", str(value or ""))
    return tuple(int(item) for item in numbers[:4]) or (0,)


def is_newer_release(tag_name: str | None) -> bool:
    latest = _release_version(tag_name)
    current = _release_version(APP_RELEASE)
    size = max(len(latest), len(current))
    return latest + (0,) * (size - len(latest)) > current + (0,) * (size - len(current))


def _configuration_row(db: Session) -> SystemPreference | None:
    return db.get(SystemPreference, UPDATE_CONFIGURATION_KEY)


def _configured_token(row: SystemPreference | None) -> str | None:
    settings_token = str(get_settings().update_github_token or "").strip()
    if settings_token:
        return settings_token
    value = row.value if row and isinstance(row.value, dict) else {}
    encrypted = value.get("github_token_encrypted")
    if not encrypted:
        return None
    try:
        return decrypt_text(str(encrypted)).strip() or None
    except Exception:
        return None


def get_update_configuration(db: Session, *, include_token: bool = False) -> dict[str, Any]:
    row = _configuration_row(db)
    stored = row.value if row and isinstance(row.value, dict) else {}
    repository = normalize_repository(stored.get("repository") or get_settings().update_repository)
    channel = str(stored.get("channel") or get_settings().update_channel or "stable").lower()
    channel = channel if channel in {"stable", "beta"} else "stable"
    token = _configured_token(row)
    result = {
        "repository": repository,
        "channel": channel,
        "configured": bool(repository),
        "has_token": bool(token),
        "current_version": APP_RELEASE,
    }
    if include_token:
        result["github_token"] = token
    return result


def save_update_configuration(db: Session, repository: str, channel: str, github_token: str | None = None) -> dict[str, Any]:
    repository = normalize_repository(repository)
    if not repository:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="请填写 GitHub 仓库")
    channel = str(channel or "stable").lower()
    if channel not in {"stable", "beta"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="更新通道只能是 stable 或 beta")
    row = _configuration_row(db)
    current = row.value if row and isinstance(row.value, dict) else {}
    value = {"repository": repository, "channel": channel}
    token = str(github_token or "").strip()
    if token:
        value["github_token_encrypted"] = encrypt_text(token)
    elif current.get("github_token_encrypted"):
        value["github_token_encrypted"] = current["github_token_encrypted"]
    if row is None:
        row = SystemPreference(key=UPDATE_CONFIGURATION_KEY, value=value)
        db.add(row)
    else:
        row.value = value
    db.flush()
    return get_update_configuration(db)


def _github_headers(token: str | None, accept: str = "application/vnd.github+json") -> dict[str, str]:
    headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "Student-Management-System-Updater"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_tls_context() -> ssl.SSLContext:
    """Use the Windows/macOS system trust store for GitHub Release TLS checks."""
    if truststore is not None:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ssl.create_default_context()


def _release_asset(release: dict[str, Any], name: str) -> dict[str, Any] | None:
    return next((asset for asset in (release.get("assets") or []) if isinstance(asset, dict) and asset.get("name") == name), None)


def serialize_release(release: dict[str, Any]) -> dict[str, Any]:
    package = _release_asset(release, UPDATE_PACKAGE_ASSET)
    checksum = _release_asset(release, UPDATE_CHECKSUM_ASSET)
    return {
        "id": release.get("id"),
        "tag_name": release.get("tag_name"),
        "name": release.get("name") or release.get("tag_name"),
        "body": str(release.get("body") or "")[:12000],
        "published_at": release.get("published_at"),
        "prerelease": bool(release.get("prerelease")),
        "package": {"name": package.get("name"), "size": package.get("size"), "url": package.get("url"), "browser_url": package.get("browser_download_url")} if package else None,
        "checksum": {"name": checksum.get("name"), "size": checksum.get("size"), "url": checksum.get("url"), "browser_url": checksum.get("browser_download_url")} if checksum else None,
        "update_ready": bool(package and checksum),
        "is_newer": is_newer_release(str(release.get("tag_name") or "")),
    }


def _select_release(releases: list[Any], channel: str) -> dict[str, Any] | None:
    candidates = [
        item
        for item in releases
        if isinstance(item, dict)
        and not item.get("draft")
        and (channel == "beta" or not item.get("prerelease"))
    ]
    return max(candidates, key=lambda item: _release_version(str(item.get("tag_name") or "")), default=None)


def check_for_update(db: Session) -> dict[str, Any]:
    config = get_update_configuration(db, include_token=True)
    if not config["configured"]:
        return {"configured": False, "current_version": APP_RELEASE, "message": "尚未配置 GitHub 更新仓库", "release": None}
    url = f"https://api.github.com/repos/{config['repository']}/releases?per_page=20"
    try:
        with httpx.Client(timeout=15, follow_redirects=True, verify=_github_tls_context()) as client:
            response = client.get(url, headers=_github_headers(config.get("github_token")))
            response.raise_for_status()
            releases = response.json()
    except httpx.HTTPError as exc:
        return {"configured": True, "current_version": APP_RELEASE, "message": f"无法连接 GitHub Release：{exc}", "release": None}
    if not isinstance(releases, list):
        return {"configured": True, "current_version": APP_RELEASE, "message": "GitHub Release 返回格式不正确", "release": None}
    release = _select_release(releases, config["channel"])
    return {
        "configured": True,
        "repository": config["repository"],
        "channel": config["channel"],
        "current_version": APP_RELEASE,
        "message": "已检查 GitHub Release",
        "release": serialize_release(release) if release else None,
    }


def _job_directory(job_id: str) -> Path:
    target = update_run_root() / job_id
    target.mkdir(parents=True, exist_ok=True)
    return target


def create_update_job(release: dict[str, Any] | None, *, requested_by_id: int, offline_package: Path | None = None) -> tuple[Path, dict[str, Any]]:
    job_id = str(uuid4())
    directory = _job_directory(job_id)
    job: dict[str, Any] = {
        "job_id": job_id,
        "project_root": str(project_root()),
        "requested_by_id": requested_by_id,
        "requested_at": china_now().isoformat(),
        "current_version": APP_RELEASE,
        "status_path": str(update_status_path()),
        "package_name": UPDATE_PACKAGE_ASSET,
        "source": "offline" if offline_package else "github_release",
    }
    if offline_package:
        job["offline_package"] = str(offline_package)
        job["offline_checksum"] = _sha256_file(offline_package)
    else:
        if not release or not release.get("package") or not release.get("checksum"):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Release 缺少受控更新包或 SHA-256 校验文件")
        job["release"] = release
    target = directory / "job.json"
    target.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
    return target, job


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def launch_update_runner(job_path: Path, github_token: str | None = None) -> None:
    if os.name != "nt":
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="当前在线更新器仅支持 Windows 本地部署")
    runner_source = project_root() / "scripts" / "update-system.ps1"
    if not runner_source.is_file():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新器脚本不存在")
    runner = job_path.parent / "update-system.ps1"
    shutil.copy2(runner_source, runner)
    environment = os.environ.copy()
    if github_token:
        environment["SMS_UPDATE_GITHUB_TOKEN"] = github_token
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(runner), "-JobPath", str(job_path)],
        cwd=str(project_root()),
        env=environment,
        creationflags=creation_flags,
        close_fds=True,
    )
