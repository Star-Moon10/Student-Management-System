import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_china_time
from app.db import engine
from app.models import (
    DeletedStudent,
    FieldProvenance,
    ImportBatch,
    ImportMatchReview,
    ImportPreview,
    QualityIssueCase,
    RelatedInfoCandidate,
    SourceDocument,
    Student,
    StudentMerge,
    StudentRelatedInfoCard,
    StudentVersion,
    SystemBackup,
    User,
    WordImportCandidate,
    utcnow,
)
from app.services.crypto import decrypt_bytes, encrypt_bytes


def _as_china_time(value: datetime | None) -> datetime | None:
    return as_china_time(value)


def _backup_filename() -> str:
    suffix = ".zip.enc" if get_settings().backup_encrypt else ".zip"
    return f"student_management_{utcnow():%Y%m%d_%H%M%S}{suffix}"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_expired_backups(db: Session) -> None:
    settings = get_settings()
    cutoff = utcnow() - timedelta(days=max(1, settings.backup_retention_days))
    for backup in db.scalars(select(SystemBackup).where(SystemBackup.created_at < cutoff)):
        if backup.storage_path:
            Path(backup.storage_path).unlink(missing_ok=True)
        db.delete(backup)


def _managed_backup_target(path_value: str | None, root: Path, label: str) -> Path | None:
    """Resolve a backup file only when it remains inside its managed directory."""
    if not path_value:
        return None
    target = Path(path_value).resolve()
    managed_root = root.resolve()
    if target == managed_root or managed_root not in target.parents:
        raise RuntimeError(f"{label}路径不在受管备份目录中，已拒绝删除")
    if target.exists() and not target.is_file():
        raise RuntimeError(f"{label}不是有效的备份文件，已拒绝删除")
    return target


def delete_database_backup(backup: SystemBackup) -> dict[str, int]:
    """Remove the managed local/off-site backup files before their database record."""
    settings = get_settings()
    targets: list[Path] = []
    local_target = _managed_backup_target(backup.storage_path, settings.backup_path, "本地备份")
    if local_target:
        targets.append(local_target)

    offsite = (backup.manifest or {}).get("offsite")
    offsite_path = offsite.get("path") if isinstance(offsite, dict) and offsite.get("status") == "completed" else None
    if offsite_path:
        if not settings.backup_offsite_path:
            raise RuntimeError("该备份存在异地副本，请先配置 BACKUP_OFFSITE_PATH 后再删除")
        offsite_target = _managed_backup_target(str(offsite_path), settings.backup_offsite_path, "异地备份")
        if offsite_target and offsite_target not in targets:
            targets.append(offsite_target)

    removed_files = 0
    for target in targets:
        if target.is_file():
            target.unlink()
            removed_files += 1
    return {"removed_files": removed_files, "offsite_files": int(bool(offsite_path))}


def _copy_offsite_backup(source: Path) -> dict[str, Any] | None:
    """Copy the already encrypted package to a mounted off-site location."""
    destination_root = get_settings().backup_offsite_path
    if not destination_root:
        return None
    destination_root.mkdir(parents=True, exist_ok=True)
    destination = destination_root / source.name
    shutil.copy2(source, destination)
    if _sha256_file(source) != _sha256_file(destination):
        destination.unlink(missing_ok=True)
        raise RuntimeError("异地备份校验和不匹配")
    return {"status": "completed", "path": str(destination), "checksum": _sha256_file(destination)}


def _backup_sqlite(target: Path) -> None:
    database_path = engine.url.database
    if not database_path or database_path == ":memory:":
        raise RuntimeError("内存数据库不支持文件备份")
    source = sqlite3.connect(database_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()


def _backup_mysql(target: Path) -> None:
    executable = shutil.which("mysqldump")
    if not executable:
        raise RuntimeError("未找到 mysqldump，无法备份 MySQL 数据库")
    url = engine.url
    if not url.database:
        raise RuntimeError("MySQL 数据库名称缺失")
    command = [executable, "--single-transaction", "--routines", "--events", f"--host={url.host or '127.0.0.1'}", f"--port={url.port or 3306}", f"--user={url.username or ''}", url.database]
    environment = os.environ.copy()
    if url.password:
        environment["MYSQL_PWD"] = url.password
    with target.open("wb") as output:
        completed = subprocess.run(command, stdout=output, stderr=subprocess.PIPE, check=False, env=environment, timeout=300)
    if completed.returncode:
        target.unlink(missing_ok=True)
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip() or "mysqldump 执行失败")


def _mysql_client_command(database: str | None = None) -> tuple[list[str], dict[str, str]]:
    executable = shutil.which("mysql")
    if not executable:
        raise RuntimeError("未找到 mysql 客户端，无法执行 MySQL 隔离恢复演练")
    url = engine.url
    command = [executable, f"--host={url.host or '127.0.0.1'}", f"--port={url.port or 3306}", f"--user={url.username or ''}", "--protocol=tcp"]
    if database:
        command.append(f"--database={database}")
    environment = os.environ.copy()
    if url.password:
        environment["MYSQL_PWD"] = url.password
    return command, environment


def _run_mysql(command: list[str], environment: dict[str, str], *, input_file: Path | None = None) -> str:
    if input_file:
        with input_file.open("rb") as source:
            completed = subprocess.run(command, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=environment, timeout=300)
    else:
        completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=environment, timeout=300)
    if completed.returncode:
        raise RuntimeError(completed.stderr.decode("utf-8", errors="replace").strip() or "MySQL 命令执行失败")
    return completed.stdout.decode("utf-8", errors="replace").strip()


def _drill_mysql_restore(restored_database: Path) -> dict[str, Any]:
    """Restore a MySQL dump into a throw-away database and always drop it."""
    temporary_name = f"sms_restore_drill_{utcnow():%Y%m%d%H%M%S}_{os.getpid()}".lower()
    command, environment = _mysql_client_command()
    created = False
    try:
        _run_mysql([*command, "-e", f"CREATE DATABASE `{temporary_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"], environment)
        created = True
        import_command, _ = _mysql_client_command(temporary_name)
        _run_mysql(import_command, environment, input_file=restored_database)
        query_command, _ = _mysql_client_command(temporary_name)
        table_count = int(_run_mysql([*query_command, "--batch", "--skip-column-names", "-e", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE()"], environment) or 0)
        student_exists = int(_run_mysql([*query_command, "--batch", "--skip-column-names", "-e", "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'students'"], environment) or 0)
        student_count = int(_run_mysql([*query_command, "--batch", "--skip-column-names", "-e", "SELECT COUNT(*) FROM students"], environment) or 0) if student_exists else 0
        missing_output = _run_mysql([*query_command, "--batch", "--skip-column-names", "-e", f"SELECT table_name FROM (SELECT 'users' AS table_name UNION ALL SELECT 'students' UNION ALL SELECT 'audit_logs' UNION ALL SELECT 'source_documents' UNION ALL SELECT 'import_batches') AS required_tables WHERE table_name NOT IN (SELECT table_name FROM information_schema.tables WHERE table_schema = DATABASE())"], environment)
        missing_tables = [line.strip() for line in missing_output.splitlines() if line.strip()]
        if missing_tables:
            raise RuntimeError(f"隔离恢复完整性检查失败：缺少表 {', '.join(missing_tables)}")
        return {"database": "mysql", "integrity": "temporary_database_restored", "table_count": table_count, "student_count": student_count, "missing_tables": [], "temporary_database": temporary_name}
    finally:
        if created:
            try:
                _run_mysql([*command, "-e", f"DROP DATABASE IF EXISTS `{temporary_name}`"], environment)
            except RuntimeError:
                # Do not obscure the actual drill result. A warning is retained by
                # the calling audit record when the drill itself fails.
                pass


def _write_package(target: Path, database_dump: Path, dialect: str) -> dict[str, Any]:
    settings = get_settings()
    database_member = f"database/student_management.{database_dump.suffix.lstrip('.')}"
    manifest: dict[str, Any] = {"version": 2, "created_at": utcnow().isoformat(), "database_dialect": dialect, "database": {"path": database_member, "sha256": _sha256_file(database_dump), "size_bytes": database_dump.stat().st_size}, "storage_files": []}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(database_dump, database_member)
        if settings.storage_path.exists():
            for item in settings.storage_path.rglob("*"):
                if not item.is_file():
                    continue
                relative = item.relative_to(settings.storage_path).as_posix()
                member = f"storage/{relative}"
                archive.write(item, member)
                manifest["storage_files"].append({"path": member, "sha256": _sha256_file(item), "size_bytes": item.stat().st_size})
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")))
    return manifest


def _decrypted_archive(source: Path, temporary_root: Path) -> Path:
    if source.suffix.lower() != ".enc":
        return source
    target = temporary_root / "backup.zip"
    target.write_bytes(decrypt_bytes(source.read_bytes()))
    return target


def create_database_backup(db: Session, actor: User | None = None) -> SystemBackup:
    settings = get_settings()
    settings.backup_path.mkdir(parents=True, exist_ok=True)
    dialect = engine.dialect.name
    target = settings.backup_path / _backup_filename()
    record = SystemBackup(database_dialect=dialect, status="processing", created_by_id=actor.id if actor else None)
    db.add(record)
    db.flush()
    try:
        with tempfile.TemporaryDirectory(prefix="sms_backup_") as temporary:
            temporary_root = Path(temporary)
            dump = temporary_root / ("database.db" if dialect == "sqlite" else "database.sql")
            if dialect == "sqlite":
                _backup_sqlite(dump)
            elif dialect == "mysql":
                _backup_mysql(dump)
            else:
                raise RuntimeError(f"暂不支持 {dialect} 数据库的自动备份")
            package = temporary_root / "backup.zip"
            manifest = _write_package(package, dump, dialect)
            manifest["encrypted"] = bool(settings.backup_encrypt)
            if settings.backup_encrypt:
                target.write_bytes(encrypt_bytes(package.read_bytes()))
            else:
                package.replace(target)
        record.file_name = target.name
        record.storage_path = str(target)
        record.size_bytes = target.stat().st_size
        record.checksum = _sha256_file(target)
        record.manifest = manifest
        record.validation_status = "valid"
        record.validated_at = utcnow()
        record.status = "completed"
        try:
            offsite = _copy_offsite_backup(target)
            if offsite:
                record.manifest = (record.manifest or {}) | {"offsite": offsite}
        except Exception as exc:
            # The local encrypted package remains valid and recoverable. Surface
            # a monitoring alert instead of discarding a successful backup.
            record.manifest = (record.manifest or {}) | {"offsite": {"status": "failed", "detail": str(exc)[:500]}}
    except Exception as exc:
        target.unlink(missing_ok=True)
        record.status = "failed"
        record.error_message = str(exc)[:1000]
    _remove_expired_backups(db)
    db.flush()
    return record


def _safe_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    for member in members:
        path = Path(member.filename)
        if path.is_absolute() or ".." in path.parts:
            raise RuntimeError("备份包包含不安全的文件路径")
    return members


def validate_backup(backup: SystemBackup) -> dict[str, Any]:
    if not backup.storage_path:
        raise RuntimeError("备份文件不存在")
    target = Path(backup.storage_path)
    if not target.is_file():
        raise RuntimeError("备份文件不存在")
    if backup.checksum and _sha256_file(target) != backup.checksum:
        raise RuntimeError("备份包校验和不匹配")
    with tempfile.TemporaryDirectory(prefix="sms_validate_") as temporary:
        with zipfile.ZipFile(_decrypted_archive(target, Path(temporary))) as archive:
            _safe_members(archive)
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (KeyError, json.JSONDecodeError) as exc:
                raise RuntimeError("备份包缺少有效清单") from exc
            database = manifest.get("database") or {}
            data = archive.read(str(database.get("path") or ""))
            if hashlib.sha256(data).hexdigest() != database.get("sha256"):
                raise RuntimeError("数据库备份内容校验失败")
            for item in manifest.get("storage_files") or []:
                data = archive.read(str(item.get("path") or ""))
                if hashlib.sha256(data).hexdigest() != item.get("sha256"):
                    raise RuntimeError(f"原始文件校验失败: {item.get('path')}")
    return manifest


def drill_restore_backup(backup: SystemBackup) -> dict[str, Any]:
    """Validate a backup by opening its database in an isolated temporary path."""
    manifest = validate_backup(backup)
    database = manifest.get("database") or {}
    with tempfile.TemporaryDirectory(prefix="sms_restore_drill_") as temporary:
        temporary_root = Path(temporary)
        archive_path = _decrypted_archive(Path(backup.storage_path or ""), temporary_root)
        with zipfile.ZipFile(archive_path) as archive:
            database_member = str(database.get("path") or "")
            restored_database = temporary_root / ("drill.db" if backup.database_dialect == "sqlite" else "drill.sql")
            restored_database.write_bytes(archive.read(database_member))
        if backup.database_dialect == "sqlite":
            connection = sqlite3.connect(restored_database)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                tables = connection.execute("SELECT count(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]
                table_names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
                student_count = int(connection.execute("SELECT count(*) FROM students").fetchone()[0]) if "students" in table_names else 0
                foreign_key_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
                required_tables = {"users", "students", "audit_logs", "source_documents", "import_batches"}
                missing_tables = sorted(required_tables - table_names)
            finally:
                connection.close()
            if integrity != "ok":
                raise RuntimeError(f"隔离恢复校验失败: {integrity}")
            if foreign_key_errors or missing_tables:
                raise RuntimeError(f"隔离恢复完整性检查失败：外键错误 {foreign_key_errors} 条，缺少表 {', '.join(missing_tables) or '无'}")
            return {"database": "sqlite", "integrity": integrity, "table_count": tables, "student_count": student_count, "foreign_key_errors": foreign_key_errors, "missing_tables": missing_tables, "storage_files": len(manifest.get("storage_files") or [])}
        if restored_database.stat().st_size <= 0:
            raise RuntimeError("隔离恢复校验失败: SQL 备份为空")
        if backup.database_dialect == "mysql":
            result = _drill_mysql_restore(restored_database)
            return {**result, "storage_files": len(manifest.get("storage_files") or [])}
        sql_text = restored_database.read_text(encoding="utf-8", errors="replace")
        table_names = set(re.findall(r"CREATE TABLE `?([A-Za-z0-9_]+)`?", sql_text, re.IGNORECASE))
        student_insert_rows = len(re.findall(r"INSERT INTO `?students`?", sql_text, re.IGNORECASE))
        return {"database": backup.database_dialect, "integrity": "sql_dump_readable", "table_count": len(table_names), "student_count": None, "student_insert_statements": student_insert_rows, "size_bytes": restored_database.stat().st_size, "storage_files": len(manifest.get("storage_files") or [])}


_STUDENT_DATA_TABLES = (
    "students",
    "source_documents",
    "import_batches",
    "import_previews",
    "field_provenance",
    "word_import_candidates",
    "related_info_candidates",
    "import_match_reviews",
    "student_related_info_cards",
    "student_versions",
    "student_merges",
    "deleted_students",
    "quality_issue_cases",
)


def _sqlite_table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()]


def _copy_sqlite_student_data(source_path: Path, db: Session) -> dict[str, int]:
    """Replace only student-domain rows, leaving current system records untouched."""
    source = sqlite3.connect(source_path)
    source.row_factory = sqlite3.Row
    restored: dict[str, int] = {}
    current_tables = set()
    try:
        current_tables = {str(row[0]) for row in source.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
        if "students" not in current_tables:
            raise RuntimeError("备份中没有学生档案表，已拒绝恢复")

        # Delete dependent records first. System-level tables such as users,
        # audit_logs, AI conversations, login events, preferences and backups are
        # intentionally never included here.
        for model in (
            QualityIssueCase,
            FieldProvenance,
            StudentRelatedInfoCard,
            RelatedInfoCandidate,
            WordImportCandidate,
            ImportMatchReview,
            ImportPreview,
            StudentVersion,
            StudentMerge,
            DeletedStudent,
            ImportBatch,
            SourceDocument,
            Student,
        ):
            db.execute(delete(model))
        db.flush()

        # Inserts use the column intersection so a valid older backup can be
        # restored after new nullable application columns were introduced.
        for table_name in _STUDENT_DATA_TABLES:
            if table_name not in current_tables:
                restored[table_name] = 0
                continue
            source_columns = _sqlite_table_columns(source, table_name)
            destination_columns = {
                str(row[1])
                for row in db.connection().connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            }
            columns = [column for column in source_columns if column in destination_columns]
            if not columns:
                restored[table_name] = 0
                continue
            quoted_columns = ", ".join(f'"{column}"' for column in columns)
            rows = source.execute(f'SELECT {quoted_columns} FROM "{table_name}"').fetchall()
            if rows:
                placeholders = ", ".join(f":{column}" for column in columns)
                db.execute(
                    text(f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'),
                    [{column: row[column] for column in columns} for row in rows],
                )
            restored[table_name] = len(rows)
        db.flush()
    finally:
        source.close()
    return restored


def restore_backup(db: Session, backup: SystemBackup) -> dict[str, Any]:
    """Restore student-domain data while preserving all current system records."""
    if backup.database_dialect != "sqlite" or engine.dialect.name != "sqlite":
        raise RuntimeError("当前恢复功能仅支持 SQLite；MySQL 请在维护窗口使用数据库工具恢复")
    manifest = validate_backup(backup)
    with tempfile.TemporaryDirectory(prefix="sms_restore_") as temporary:
        temporary_root = Path(temporary)
        archive_path = _decrypted_archive(Path(backup.storage_path), temporary_root)
        with zipfile.ZipFile(archive_path) as archive:
            _safe_members(archive)
            database_member = str((manifest.get("database") or {}).get("path"))
            extracted_database = temporary_root / "restore.db"
            extracted_database.write_bytes(archive.read(database_member))
            restored_tables = _copy_sqlite_student_data(extracted_database, db)
            storage_root = get_settings().storage_path.resolve()
            restored_storage_files = 0
            for item in manifest.get("storage_files") or []:
                member = str(item.get("path") or "")
                try:
                    relative = Path(member).relative_to("storage")
                except ValueError as exc:
                    raise RuntimeError("恢复文件路径不安全") from exc
                target = (storage_root / relative).resolve()
                if storage_root not in target.parents:
                    raise RuntimeError("恢复文件路径不安全")
                # A current file is never replaced by an older backup. This keeps
                # newly imported original files and all later lineage intact.
                if target.exists():
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
                restored_storage_files += 1
    return {
        "database": "student_data_restored",
        "restored_tables": restored_tables,
        "student_count": restored_tables.get("students", 0),
        "storage_files": restored_storage_files,
        "preserved_system_data": ["users", "audit_logs", "ai_conversations", "login_security_events", "system_preferences", "system_backups", "background_tasks"],
    }


def maybe_create_scheduled_backup(db: Session) -> SystemBackup | None:
    settings = get_settings()
    latest = db.scalar(select(SystemBackup).where(SystemBackup.status == "completed").order_by(SystemBackup.created_at.desc()).limit(1))
    latest_created_at = _as_china_time(latest.created_at) if latest else None
    if latest and latest_created_at and latest_created_at >= utcnow() - timedelta(hours=max(1, settings.backup_interval_hours)):
        _remove_expired_backups(db)
        return None
    return create_database_backup(db)
