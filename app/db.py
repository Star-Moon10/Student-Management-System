import json
import re
import sqlite3
from collections.abc import Generator
from datetime import datetime
from pathlib import Path

from sqlalchemy import JSON, DateTime, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings
from app.core.time import TIMEZONE_MIGRATION_KEY, china_now, legacy_utc_to_china


def _make_engine():
    database_url = get_settings().database_url
    if database_url.startswith("sqlite:///") and database_url != "sqlite:///:memory:":
        database_file = database_url.removeprefix("sqlite:///").split("?", maxsplit=1)[0]
        Path(database_file).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app import models  # noqa: F401
    from app.services.crypto import blind_index, encrypt_text

    Base.metadata.create_all(bind=engine)
    columns = {column["name"] for column in inspect(engine).get_columns("students")}
    indexes = {index["name"] for index in inspect(engine).get_indexes("students")}
    user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    user_indexes = {index["name"] for index in inspect(engine).get_indexes("users")}
    related_candidate_columns = {column["name"] for column in inspect(engine).get_columns("related_info_candidates")}
    ai_message_columns = {column["name"] for column in inspect(engine).get_columns("ai_conversation_messages")}
    audit_columns = {column["name"] for column in inspect(engine).get_columns("audit_logs")}
    audit_indexes = {index["name"] for index in inspect(engine).get_indexes("audit_logs")}
    backup_columns = {column["name"] for column in inspect(engine).get_columns("system_backups")}
    import_batch_columns = {column["name"] for column in inspect(engine).get_columns("import_batches")}
    source_document_columns = {column["name"] for column in inspect(engine).get_columns("source_documents")}

    table_columns = {
        table_name: {column["name"] for column in inspect(engine).get_columns(table_name)}
        for table_name in (
            "import_previews",
            "field_provenance",
            "word_import_candidates",
            "related_info_candidates",
            "student_related_info_cards",
            "audit_logs",
        )
    }

    def table_has_column(table_name: str, column_name: str) -> bool:
        return column_name in table_columns.get(table_name, set())
    renamed_columns = {
        "major": ("school_major", "VARCHAR(128)"),
        "class_name": ("current_class", "VARCHAR(64)"),
        "phone": ("mobile_phone", "VARCHAR(32)"),
        "email": ("electronic_email", "VARCHAR(255)"),
        "address": ("family_address", "VARCHAR(500)"),
    }
    renamed_field_names = {old_name: new_name for old_name, (new_name, _) in renamed_columns.items()}
    profile_columns = {
        "candidate_no": "VARCHAR(64)",
        "national_id": "VARCHAR(32)",
        "student_origin": "VARCHAR(255)",
        "ethnicity": "VARCHAR(64)",
        "political_status": "VARCHAR(64)",
        "enrollment_date": "DATE",
        "graduation_year": "VARCHAR(16)",
        "graduation_date": "DATE",
        "urban_rural_origin": "VARCHAR(32)",
        "pre_enrollment_archive_unit": "VARCHAR(255)",
        "archive_transferred": "VARCHAR(16)",
        "pre_enrollment_police_station": "VARCHAR(255)",
        "household_registration_transferred": "VARCHAR(16)",
        "education_level": "VARCHAR(64)",
        "program_duration": "VARCHAR(32)",
        "school": "VARCHAR(128)",
        "college": "VARCHAR(128)",
        "school_major": "VARCHAR(128)",
        "major_direction": "VARCHAR(128)",
        "current_class": "VARCHAR(64)",
        "training_mode": "VARCHAR(64)",
        "commissioned_unit": "VARCHAR(255)",
        "hardship_category": "VARCHAR(64)",
        "normal_student_category": "VARCHAR(64)",
        "mobile_phone": "VARCHAR(32)",
        "electronic_email": "VARCHAR(255)",
        "qq_number": "VARCHAR(32)",
        "family_phone": "VARCHAR(32)",
        "family_postcode": "VARCHAR(16)",
        "family_address": "VARCHAR(500)",
        "poverty_county_52": "VARCHAR(16)",
        "poverty_county_province": "VARCHAR(64)",
        "poverty_county_city": "VARCHAR(64)",
        "poverty_county_district": "VARCHAR(64)",
        "registered_poor": "VARCHAR(16)",
        "study_mode": "VARCHAR(64)",
        "vocational_expansion_flag": "VARCHAR(16)",
        "remarks": "TEXT",
    }
    with engine.begin() as connection:
        # The read-only guest role was removed. Preserve old installations by
        # converting those accounts to the least-privileged active role.
        connection.execute(text("UPDATE users SET role = 'TEACHER' WHERE role IN ('VIEWER', 'viewer')"))
        if "permissions" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN permissions JSON"))
            user_columns.add("permissions")
        for column, column_type in {
            "session_version": "INTEGER NOT NULL DEFAULT 1",
            "must_change_password": "BOOLEAN NOT NULL DEFAULT 0",
            "password_changed_at": "DATETIME",
            "mfa_secret": "TEXT",
            "mfa_enabled": "BOOLEAN NOT NULL DEFAULT 0",
        }.items():
            if column not in user_columns:
                connection.execute(text(f"ALTER TABLE users ADD COLUMN {column} {column_type}"))
                user_columns.add(column)
        if "super_admin_key" not in user_columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN super_admin_key VARCHAR(16)"))
            user_columns.add("super_admin_key")
        if "content_type" not in related_candidate_columns:
            connection.execute(text("ALTER TABLE related_info_candidates ADD COLUMN content_type VARCHAR(24) NOT NULL DEFAULT 'text'"))
            related_candidate_columns.add("content_type")
        if "excel_payload" not in related_candidate_columns:
            connection.execute(text("ALTER TABLE related_info_candidates ADD COLUMN excel_payload JSON"))
            related_candidate_columns.add("excel_payload")
        if "sources" not in ai_message_columns:
            connection.execute(text("ALTER TABLE ai_conversation_messages ADD COLUMN sources JSON"))
            ai_message_columns.add("sources")
        if "intent" not in ai_message_columns:
            connection.execute(text("ALTER TABLE ai_conversation_messages ADD COLUMN intent VARCHAR(32)"))
            ai_message_columns.add("intent")
        for column, column_type in {
            "model_name": "VARCHAR(128)",
            "duration_ms": "INTEGER",
        }.items():
            if column not in ai_message_columns:
                connection.execute(text(f"ALTER TABLE ai_conversation_messages ADD COLUMN {column} {column_type}"))
                ai_message_columns.add(column)
        for column, column_type in {
            "rollback_data": "TEXT",
            "rollback_status": "VARCHAR(24)",
        }.items():
            if column not in import_batch_columns:
                connection.execute(text(f"ALTER TABLE import_batches ADD COLUMN {column} {column_type}"))
                import_batch_columns.add(column)
        for column, column_type in {
            "previous_hash": "VARCHAR(64)",
            "entry_hash": "VARCHAR(64)",
        }.items():
            if column not in audit_columns:
                connection.execute(text(f"ALTER TABLE audit_logs ADD COLUMN {column} {column_type}"))
                audit_columns.add(column)
        for column, column_type in {
            "checksum": "VARCHAR(64)",
            "manifest": "JSON",
            "validation_status": "VARCHAR(24)",
            "validated_at": "DATETIME",
        }.items():
            if column not in backup_columns:
                connection.execute(text(f"ALTER TABLE system_backups ADD COLUMN {column} {column_type}"))
                backup_columns.add(column)
        for column, column_type in {
            "version_group": "VARCHAR(64)",
            "version_no": "INTEGER NOT NULL DEFAULT 1",
            "tags": "JSON",
            "status": "VARCHAR(24) NOT NULL DEFAULT 'active'",
            "archived_at": "DATETIME",
        }.items():
            if column not in source_document_columns:
                connection.execute(text(f"ALTER TABLE source_documents ADD COLUMN {column} {column_type}"))
                source_document_columns.add(column)
        if engine.dialect.name == "mysql":
            connection.execute(text("ALTER TABLE users MODIFY role VARCHAR(16) NOT NULL"))

        # Legacy installations stored the bootstrap account as ADMIN. Promote the
        # earliest administrator once and keep every other administrator ordinary.
        selected_super_admin = connection.execute(
            text("SELECT id FROM users WHERE role = 'SUPER_ADMIN' ORDER BY created_at ASC, id ASC LIMIT 1")
        ).scalar()
        if selected_super_admin is None:
            selected_super_admin = connection.execute(
                text("SELECT id FROM users WHERE role = 'ADMIN' ORDER BY created_at ASC, id ASC LIMIT 1")
            ).scalar()
        connection.execute(text("UPDATE users SET super_admin_key = NULL"))
        if selected_super_admin is not None:
            connection.execute(
                text("UPDATE users SET role = 'ADMIN' WHERE role = 'SUPER_ADMIN' AND id != :id"),
                {"id": selected_super_admin},
            )
            connection.execute(
                text("UPDATE users SET role = 'SUPER_ADMIN', super_admin_key = 'super_admin' WHERE id = :id"),
                {"id": selected_super_admin},
            )
        if "uq_users_super_admin_key" not in user_indexes:
            connection.execute(text("CREATE UNIQUE INDEX uq_users_super_admin_key ON users (super_admin_key)"))

        def drop_student_index(index_name: str) -> None:
            if index_name not in indexes:
                return
            if engine.dialect.name == "mysql":
                connection.execute(text(f"ALTER TABLE students DROP INDEX {index_name}"))
            else:
                connection.execute(text(f"DROP INDEX IF EXISTS {index_name}"))
            indexes.remove(index_name)

        for old_name in {*renamed_columns, "grade", "status", "notes"}:
            drop_student_index(f"ix_students_{old_name}")
        for old_name, (new_name, column_type) in renamed_columns.items():
            if old_name not in columns:
                continue
            if new_name in columns:
                connection.execute(text(f"UPDATE students SET {new_name} = COALESCE({new_name}, {old_name})"))
                connection.execute(text(f"ALTER TABLE students DROP COLUMN {old_name}"))
            elif engine.dialect.name == "mysql":
                connection.execute(text(f"ALTER TABLE students CHANGE {old_name} {new_name} {column_type} NULL"))
            else:
                connection.execute(text(f"ALTER TABLE students RENAME COLUMN {old_name} TO {new_name}"))
            columns.remove(old_name)
            columns.add(new_name)
            connection.execute(text("UPDATE field_provenance SET field_name = :new_name WHERE field_name = :old_name"), {"old_name": old_name, "new_name": new_name})
        for column, column_type in profile_columns.items():
            if column not in columns:
                connection.execute(text(f"ALTER TABLE students ADD COLUMN {column} {column_type}"))
                columns.add(column)
        for column in {"national_id_hash", "mobile_phone_hash", "electronic_email_hash"}:
            if column not in columns:
                connection.execute(text(f"ALTER TABLE students ADD COLUMN {column} VARCHAR(64)"))
                columns.add(column)
        if engine.dialect.name == "mysql":
            for column in {"national_id", "mobile_phone", "electronic_email", "qq_number", "family_phone", "family_postcode", "family_address"}:
                connection.execute(text(f"ALTER TABLE students MODIFY {column} TEXT NULL"))
            for table_name, column_name in (
                ("import_previews", "preview_data"),
                ("field_provenance", "raw_value"),
                ("word_import_candidates", "candidate_data"),
                ("word_import_candidates", "evidence"),
                ("related_info_candidates", "extracted_identity"),
                ("related_info_candidates", "remarks"),
                ("related_info_candidates", "excel_payload"),
                ("student_related_info_cards", "excel_payload"),
                ("audit_logs", "before_data"),
                ("audit_logs", "after_data"),
            ):
                if table_has_column(table_name, column_name):
                    connection.execute(text(f"ALTER TABLE {table_name} MODIFY {column_name} TEXT NULL"))
        encrypted_fields = {
            "national_id": "national_id_hash",
            "mobile_phone": "mobile_phone_hash",
            "electronic_email": "electronic_email_hash",
            "qq_number": None,
            "family_phone": None,
            "family_postcode": None,
            "family_address": None,
        }
        for row in connection.execute(text(f"SELECT id, {', '.join(encrypted_fields)} FROM students")).mappings():
            updates: dict[str, object] = {"id": row["id"]}
            for field, hash_field in encrypted_fields.items():
                value = row[field]
                if value in (None, ""):
                    continue
                text_value = str(value)
                if not text_value.startswith("gAAAA"):
                    updates[field] = encrypt_text(text_value)
                if hash_field and not row.get(hash_field):
                    updates[hash_field] = blind_index(text_value)
            if len(updates) > 1:
                assignments = ", ".join(f"{column} = :{column}" for column in updates if column != "id")
                connection.execute(text(f"UPDATE students SET {assignments} WHERE id = :id"), updates)

        def migrate_encrypted_text(table_name: str, column_name: str) -> None:
            if not table_has_column(table_name, column_name):
                return
            for row in connection.execute(text(f"SELECT id, {column_name} FROM {table_name}")).mappings():
                value = row[column_name]
                if value in (None, "") or str(value).startswith("gAAAA"):
                    continue
                connection.execute(
                    text(f"UPDATE {table_name} SET {column_name} = :value WHERE id = :id"),
                    {"id": row["id"], "value": encrypt_text(str(value))},
                )

        def migrate_encrypted_json(table_name: str, column_name: str) -> None:
            if not table_has_column(table_name, column_name):
                return
            for row in connection.execute(text(f"SELECT id, {column_name} FROM {table_name}")).mappings():
                value = row[column_name]
                if value is None or (isinstance(value, str) and value.startswith("gAAAA")):
                    continue
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except json.JSONDecodeError:
                        pass
                payload = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
                connection.execute(
                    text(f"UPDATE {table_name} SET {column_name} = :value WHERE id = :id"),
                    {"id": row["id"], "value": encrypt_text(payload)},
                )

        for table_name, column_name in (("field_provenance", "raw_value"), ("related_info_candidates", "remarks")):
            migrate_encrypted_text(table_name, column_name)
        for table_name, column_name in (
            ("import_previews", "preview_data"),
            ("word_import_candidates", "candidate_data"),
            ("word_import_candidates", "evidence"),
            ("related_info_candidates", "extracted_identity"),
            ("related_info_candidates", "excel_payload"),
            ("student_related_info_cards", "excel_payload"),
            ("audit_logs", "before_data"),
            ("audit_logs", "after_data"),
        ):
            migrate_encrypted_json(table_name, column_name)
        for column in {"grade", "status", "notes"}:
            if column in columns:
                connection.execute(text(f"ALTER TABLE students DROP COLUMN {column}"))
        for old_name, new_name in renamed_field_names.items():
            connection.execute(text("UPDATE field_provenance SET field_name = :new_name WHERE field_name = :old_name"), {"old_name": old_name, "new_name": new_name})
        connection.execute(text("DELETE FROM field_provenance WHERE field_name IN ('grade', 'status', 'notes')"))

        for table_name, payload_column in (("import_batches", "mapping"), ("word_import_candidates", "candidate_data")):
            rows = connection.execute(text(f"SELECT id, {payload_column} FROM {table_name}")).mappings()
            for row in rows:
                payload = row[payload_column]
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        continue
                if not isinstance(payload, dict):
                    continue
                migrated = {
                    renamed_field_names.get(field_name, field_name): value
                    for field_name, value in payload.items()
                    if field_name not in {"grade", "status", "notes"}
                }
                if migrated != payload:
                    connection.execute(
                        text(f"UPDATE {table_name} SET {payload_column} = :payload WHERE id = :id"),
                        {"id": row["id"], "payload": json.dumps(migrated, ensure_ascii=False)},
                    )

        for column in {"student_no", "candidate_no", "full_name", "national_id", "national_id_hash", "mobile_phone_hash", "electronic_email_hash", "school", "college", "school_major", "current_class"}:
            index_name = f"ix_students_{column}"
            if index_name not in indexes:
                connection.execute(text(f"CREATE INDEX {index_name} ON students ({column})"))
        if "ix_audit_logs_entry_hash" not in audit_indexes:
            connection.execute(text("CREATE UNIQUE INDEX ix_audit_logs_entry_hash ON audit_logs (entry_hash)"))
    _migrate_legacy_timestamps_to_china()


_TIMESTAMP_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")


def _shift_legacy_timestamp_text(value: str) -> str:
    if not _TIMESTAMP_TEXT.fullmatch(value):
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return legacy_utc_to_china(parsed).isoformat() + "+08:00"


def _shift_embedded_timestamps(value):
    if isinstance(value, str):
        return _shift_legacy_timestamp_text(value)
    if isinstance(value, list):
        return [_shift_embedded_timestamps(item) for item in value]
    if isinstance(value, dict):
        return {key: _shift_embedded_timestamps(item) for key, item in value.items()}
    return value


def _create_pre_china_time_snapshot(bind_engine) -> str | None:
    if bind_engine.dialect.name != "sqlite" or not bind_engine.url.database or bind_engine.url.database == ":memory:":
        return None
    source_path = Path(bind_engine.url.database).resolve()
    if not source_path.is_file():
        return None
    target_root = get_settings().backup_path
    target_root.mkdir(parents=True, exist_ok=True)
    target = target_root / f"pre_china_time_migration_{china_now():%Y%m%d_%H%M%S}.sqlite"
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    return str(target)


def _migrate_legacy_timestamps_to_china(bind_engine=None, *, create_snapshot: bool = True) -> dict[str, int | str | None]:
    """Convert the legacy UTC physical values once and preserve the audit chain."""
    from app.models import AuditLog, SystemPreference
    from app.services.audit import _entry_hash
    from app.services.crypto import EncryptedJSON

    target_engine = bind_engine or engine
    with target_engine.begin() as connection:
        session = Session(bind=connection)
        try:
            if session.get(SystemPreference, TIMEZONE_MIGRATION_KEY):
                return {"migrated": 0, "json_values": 0, "audit_entries": 0, "snapshot": None}
            snapshot_path = _create_pre_china_time_snapshot(target_engine) if create_snapshot else None
            timestamp_fields = 0
            json_values = 0
            for mapper in Base.registry.mappers:
                model = mapper.class_
                for record in session.scalars(select(model)):
                    for attribute in mapper.column_attrs:
                        column = attribute.columns[0]
                        value = getattr(record, attribute.key)
                        if isinstance(column.type, DateTime) and isinstance(value, datetime):
                            setattr(record, attribute.key, legacy_utc_to_china(value))
                            timestamp_fields += 1
                        elif isinstance(column.type, (JSON, EncryptedJSON)) and value is not None:
                            shifted = _shift_embedded_timestamps(value)
                            if shifted != value:
                                setattr(record, attribute.key, shifted)
                                json_values += 1
            session.flush()

            audit_entries = list(session.scalars(select(AuditLog).order_by(AuditLog.id.asc())))
            for entry in audit_entries:
                entry.previous_hash = None
                entry.entry_hash = None
            session.flush()
            previous_hash = None
            for entry in audit_entries:
                entry.previous_hash = previous_hash
                entry.entry_hash = _entry_hash(entry, previous_hash)
                previous_hash = entry.entry_hash
            session.add(
                SystemPreference(
                    key=TIMEZONE_MIGRATION_KEY,
                    value={
                        "migrated_at": china_now().isoformat(),
                        "offset_hours": 8,
                        "timestamp_fields": timestamp_fields,
                        "json_values": json_values,
                        "audit_entries": len(audit_entries),
                        "snapshot": snapshot_path,
                    },
                )
            )
            session.flush()
            return {"migrated": timestamp_fields, "json_values": json_values, "audit_entries": len(audit_entries), "snapshot": snapshot_path}
        finally:
            session.close()
