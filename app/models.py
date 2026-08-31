import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.core.time import CHINA_TIMEZONE, china_now
from app.services.crypto import EncryptedJSON, EncryptedText, blind_index


def utcnow() -> datetime:
    """Legacy name retained for model defaults; persisted system time is CST."""
    return china_now()


class Role(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    TEACHER = "teacher"


class ImportStatus(str, enum.Enum):
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class CandidateStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=16), default=Role.TEACHER)
    super_admin_key: Mapped[str | None] = mapped_column(String(16), unique=True, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permissions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, default=1)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    mfa_secret: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoginSecurityEvent(Base):
    """A compact, privacy-conscious record used to review account access."""

    __tablename__ = "login_security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    network_key: Mapped[str | None] = mapped_column(String(96), nullable=True, index=True)
    device_label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_unusual: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class HighRiskApproval(Base):
    __tablename__ = "high_risk_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    approved_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    candidate_no: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(128), index=True)
    gender: Mapped[str | None] = mapped_column(String(16), nullable=True)
    national_id: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    national_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    student_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ethnicity: Mapped[str | None] = mapped_column(String(64), nullable=True)
    political_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enrollment_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    graduation_year: Mapped[str | None] = mapped_column(String(16), nullable=True)
    graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    urban_rural_origin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pre_enrollment_archive_unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archive_transferred: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pre_enrollment_police_station: Mapped[str | None] = mapped_column(String(255), nullable=True)
    household_registration_transferred: Mapped[str | None] = mapped_column(String(16), nullable=True)
    education_level: Mapped[str | None] = mapped_column(String(64), nullable=True)
    program_duration: Mapped[str | None] = mapped_column(String(32), nullable=True)
    school: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    college: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    school_major: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    major_direction: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_class: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    training_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    commissioned_unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hardship_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    normal_student_category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mobile_phone: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    mobile_phone_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    electronic_email: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    electronic_email_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    qq_number: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    family_phone: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    family_postcode: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    family_address: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    poverty_county_52: Mapped[str | None] = mapped_column(String(16), nullable=True)
    poverty_county_province: Mapped[str | None] = mapped_column(String(64), nullable=True)
    poverty_county_city: Mapped[str | None] = mapped_column(String(64), nullable=True)
    poverty_county_district: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registered_poor: Mapped[str | None] = mapped_column(String(16), nullable=True)
    study_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    vocational_expansion_flag: Mapped[str | None] = mapped_column(String(16), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


@event.listens_for(Student, "before_insert")
@event.listens_for(Student, "before_update")
def _refresh_student_sensitive_indexes(mapper, connection, target: Student) -> None:
    target.national_id_hash = blind_index(target.national_id)
    target.mobile_phone_hash = blind_index(target.mobile_phone)
    target.electronic_email_hash = blind_index(target.electronic_email)


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), unique=True)
    file_type: Mapped[str] = mapped_column(String(16))
    mime_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    version_group: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(24), default="active", index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    imported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mode: Mapped[str] = mapped_column(String(32), default="upsert")
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus), default=ImportStatus.PROCESSING)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    created_rows: Mapped[int] = mapped_column(Integer, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, default=0)
    skipped_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    rollback_data: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    rollback_status: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportPreview(Base):
    __tablename__ = "import_previews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    mode: Mapped[str] = mapped_column(String(32), default="upsert")
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    preview_data: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    applied_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FieldProvenance(Base):
    __tablename__ = "field_provenance"
    __table_args__ = (UniqueConstraint("student_id", "import_batch_id", "field_name", name="uq_provenance_field_batch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    source_document_id: Mapped[int | None] = mapped_column(ForeignKey("source_documents.id"), nullable=True)
    import_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), nullable=True)
    field_name: Mapped[str] = mapped_column(String(64), index=True)
    source_sheet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_column: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_value: Mapped[str | None] = mapped_column(EncryptedText(), nullable=True)
    confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WordImportCandidate(Base):
    __tablename__ = "word_import_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    candidate_data: Mapped[dict] = mapped_column(EncryptedJSON())
    evidence: Mapped[list] = mapped_column(EncryptedJSON(), default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[CandidateStatus] = mapped_column(Enum(CandidateStatus), default=CandidateStatus.PENDING)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RelatedInfoCandidate(Base):
    __tablename__ = "related_info_candidates"
    __table_args__ = (UniqueConstraint("import_batch_id", "student_id", name="uq_related_info_candidate_student_batch"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    extracted_identity: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    remarks: Mapped[str] = mapped_column(EncryptedText())
    content_type: Mapped[str] = mapped_column(String(24), default="text")
    excel_payload: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    source_sheet: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_locator: Mapped[str] = mapped_column(String(255))
    confidence: Mapped[int] = mapped_column(Integer, default=85)
    status: Mapped[CandidateStatus] = mapped_column(Enum(CandidateStatus), default=CandidateStatus.PENDING)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ImportMatchReview(Base):
    """A source row that needs a human to choose the matching student."""

    __tablename__ = "import_match_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    identity: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    payload: Mapped[dict] = mapped_column(EncryptedJSON(), default=dict)
    candidate_student_ids: Mapped[list] = mapped_column(JSON, default=list)
    match_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    matched_student_id: Mapped[int | None] = mapped_column(ForeignKey("students.id"), nullable=True, index=True)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StudentRelatedInfoCard(Base):
    __tablename__ = "student_related_info_cards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    source_document_id: Mapped[int] = mapped_column(ForeignKey("source_documents.id"), index=True)
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    imported_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    excel_payload: Mapped[dict] = mapped_column(EncryptedJSON())
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StudentVersion(Base):
    __tablename__ = "student_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(EncryptedJSON())
    changed_fields: Mapped[list] = mapped_column(JSON, default=list)
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class StudentMerge(Base):
    __tablename__ = "student_merges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_student_no: Mapped[str] = mapped_column(String(64), index=True)
    source_full_name: Mapped[str] = mapped_column(String(128))
    target_student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    target_student_no: Mapped[str] = mapped_column(String(64), index=True)
    source_snapshot: Mapped[dict] = mapped_column(EncryptedJSON())
    merged_fields: Mapped[list] = mapped_column(JSON, default=list)
    merged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class DeletedStudent(Base):
    __tablename__ = "deleted_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_student_id: Mapped[int] = mapped_column(Integer, index=True)
    student_no: Mapped[str] = mapped_column(String(64), index=True)
    full_name: Mapped[str] = mapped_column(String(128))
    snapshot: Mapped[dict] = mapped_column(EncryptedJSON())
    related_cards: Mapped[list] = mapped_column(EncryptedJSON(), default=list)
    deleted_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restored_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(64), index=True)
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    before_data: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    after_data: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    entry_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AuditReversal(Base):
    __tablename__ = "audit_reversals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_log_id: Mapped[int] = mapped_column(ForeignKey("audit_logs.id"), unique=True, index=True)
    undone_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class SystemBackup(Base):
    __tablename__ = "system_backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    database_dialect: Mapped[str] = mapped_column(String(32), default="sqlite")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    manifest: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    validation_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="completed", index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AiConversation(Base):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, index=True)


class AiConversationMessage(Base):
    __tablename__ = "ai_conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("ai_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    sources: Mapped[list] = mapped_column(JSON, default=list)
    intent: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AiPendingAction(Base):
    __tablename__ = "ai_pending_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    conversation_id: Mapped[str | None] = mapped_column(ForeignKey("ai_conversations.id"), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SystemPreference(Base):
    __tablename__ = "system_preferences"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserDataScope(Base):
    __tablename__ = "user_data_scopes"
    __table_args__ = (UniqueConstraint("user_id", name="uq_user_data_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    school: Mapped[str | None] = mapped_column(String(128), nullable=True)
    college: Mapped[str | None] = mapped_column(String(128), nullable=True)
    school_major: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class UserDataScopeRule(Base):
    __tablename__ = "user_data_scope_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    school: Mapped[str | None] = mapped_column(String(128), nullable=True)
    college: Mapped[str | None] = mapped_column(String(128), nullable=True)
    school_major: Mapped[str | None] = mapped_column(String(128), nullable=True)
    current_class: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SavedStudentFilter(Base):
    __tablename__ = "saved_student_filters"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_saved_student_filter_user_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ImportMappingTemplate(Base):
    __tablename__ = "import_mapping_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    required_fields: Mapped[list] = mapped_column(JSON, default=list)
    default_mode: Mapped[str] = mapped_column(String(24), default="upsert")
    update_policy: Mapped[str] = mapped_column(String(24), default="overwrite")
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExportTemplate(Base):
    __tablename__ = "export_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    filters: Mapped[dict] = mapped_column(JSON, default=dict)
    include_provenance: Mapped[bool] = mapped_column(Boolean, default=True)
    mask_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TemplateRevision(Base):
    __tablename__ = "template_revisions"
    __table_args__ = (UniqueConstraint("template_kind", "template_id", "revision_no", name="uq_template_revision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    template_kind: Mapped[str] = mapped_column(String(24), index=True)
    template_id: Mapped[int] = mapped_column(Integer, index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(24))
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QualityScan(Base):
    __tablename__ = "quality_scans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    issues: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class QualityIssueCase(Base):
    __tablename__ = "quality_issue_cases"
    __table_args__ = (UniqueConstraint("issue_code", "student_id", name="uq_quality_issue_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_code: Mapped[str] = mapped_column(String(64), index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SystemAlert(Base):
    __tablename__ = "system_alerts"
    __table_args__ = (UniqueConstraint("alert_key", name="uq_system_alert_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    alert_key: Mapped[str] = mapped_column(String(96), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="warning")
    title: Mapped[str] = mapped_column(String(255))
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class AiEvaluationRun(Base):
    __tablename__ = "ai_evaluation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24), default="completed")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    results: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class BackgroundTask(Base):
    __tablename__ = "background_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    task_type: Mapped[str] = mapped_column(String(48), index=True)
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str | None] = mapped_column(String(255), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
