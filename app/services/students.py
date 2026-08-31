from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_china_time
from app.models import DeletedStudent, FieldProvenance, RelatedInfoCandidate, Student, StudentRelatedInfoCard, StudentVersion, User, WordImportCandidate, utcnow
from app.schemas import StudentCreate, StudentUpdate
from app.services.crypto import blind_index

STUDENT_FIELDS = (
    "student_no",
    "candidate_no",
    "full_name",
    "gender",
    "national_id",
    "date_of_birth",
    "student_origin",
    "ethnicity",
    "political_status",
    "enrollment_date",
    "graduation_year",
    "graduation_date",
    "urban_rural_origin",
    "pre_enrollment_archive_unit",
    "archive_transferred",
    "pre_enrollment_police_station",
    "household_registration_transferred",
    "education_level",
    "program_duration",
    "school",
    "college",
    "school_major",
    "major_direction",
    "current_class",
    "training_mode",
    "commissioned_unit",
    "hardship_category",
    "normal_student_category",
    "mobile_phone",
    "electronic_email",
    "qq_number",
    "family_phone",
    "family_postcode",
    "family_address",
    "poverty_county_52",
    "poverty_county_province",
    "poverty_county_city",
    "poverty_county_district",
    "registered_poor",
    "study_mode",
    "vocational_expansion_flag",
    "remarks",
)
FILTERABLE_STUDENT_FIELDS = frozenset(STUDENT_FIELDS)
DATE_FILTER_FIELDS = {"date_of_birth", "enrollment_date", "graduation_date"}
EXCLUSION_FILTER_PREFIX = "exclude_"
SORTABLE_STUDENT_FIELDS = frozenset({"student_no", "full_name", "school", "college", "school_major", "current_class", "created_at", "updated_at"})
FILTER_OPTION_FIELDS = ("school", "college", "school_major", "current_class", "political_status")


def student_to_dict(student: Student) -> dict[str, Any]:
    return {
        field: (getattr(student, field).isoformat() if isinstance(getattr(student, field), date) else getattr(student, field))
        for field in STUDENT_FIELDS
    } | {"id": student.id, "row_version": student.row_version}


def build_student_query(
    keyword: str | None = None,
    current_class: str | None = None,
    school_major: str | None = None,
    college: str | None = None,
    school: str | None = None,
    filters: dict[str, str] | None = None,
    sort_by: str = "student_no",
    sort_direction: str = "asc",
    scope: dict[str, str] | list[dict[str, str]] | None = None,
) -> Select[tuple[Student]]:
    structured_filters = dict(filters or {})
    filter_keyword = structured_filters.pop("keyword", None)
    if not keyword and filter_keyword:
        keyword = str(filter_keyword)
    statement = select(Student)
    if keyword:
        escaped = keyword.strip().replace("%", r"\%").replace("_", r"\_")
        pattern = f"%{escaped}%"
        statement = statement.where(
            or_(
                Student.student_no.ilike(pattern),
                Student.candidate_no.ilike(pattern),
                Student.full_name.ilike(pattern),
                Student.national_id_hash == blind_index(keyword),
                Student.mobile_phone_hash == blind_index(keyword),
                Student.electronic_email_hash == blind_index(keyword),
            )
        )
    for field, value in (("current_class", current_class), ("school_major", school_major), ("college", college), ("school", school)):
        if value:
            structured_filters.setdefault(field, value)
    for field, raw_value in structured_filters.items():
        exclude = field.startswith(EXCLUSION_FILTER_PREFIX)
        target_field = field.removeprefix(EXCLUSION_FILTER_PREFIX) if exclude else field
        if exclude and target_field not in FILTERABLE_STUDENT_FIELDS:
            continue
        if (not exclude and field not in FILTERABLE_STUDENT_FIELDS) or raw_value is None:
            continue
        value = str(raw_value).strip()
        if not value:
            continue
        if exclude:
            if target_field in {"national_id", "mobile_phone", "electronic_email"}:
                hash_column = getattr(Student, f"{target_field}_hash")
                statement = statement.where(hash_column != blind_index(value))
                continue
            column = getattr(Student, target_field)
            escaped = value.replace("%", r"\%").replace("_", r"\_")
            statement = statement.where(~column.ilike(f"%{escaped}%", escape="\\"))
            continue
        if field == "remarks" and value == "*":
            statement = statement.where(Student.remarks.is_not(None), Student.remarks != "")
            continue
        if field in {"national_id", "mobile_phone", "electronic_email"}:
            hash_column = getattr(Student, f"{field}_hash")
            statement = statement.where(hash_column == blind_index(value))
            continue
        column = getattr(Student, field)
        if field in DATE_FILTER_FIELDS:
            try:
                statement = statement.where(column == date.fromisoformat(value))
            except ValueError:
                continue
        else:
            escaped = value.replace("%", r"\%").replace("_", r"\_")
            statement = statement.where(column.ilike(f"%{escaped}%", escape="\\"))
    rules = scope if isinstance(scope, list) else [scope or {}]
    valid_rules = [{field: value for field, value in rule.items() if field in {"school", "college", "school_major", "current_class"} and value} for rule in rules]
    valid_rules = [rule for rule in valid_rules if rule]
    if valid_rules:
        statement = statement.where(or_(*(and_(*(getattr(Student, field) == value for field, value in rule.items())) for rule in valid_rules)))
    if sort_by not in SORTABLE_STUDENT_FIELDS:
        sort_by = "student_no"
    order_column = getattr(Student, sort_by)
    ordering = order_column.desc() if sort_direction.lower() == "desc" else order_column.asc()
    return statement.order_by(ordering, Student.student_no.asc())


def list_students(
    db: Session,
    keyword: str | None = None,
    current_class: str | None = None,
    school_major: str | None = None,
    college: str | None = None,
    school: str | None = None,
    filters: dict[str, str] | None = None,
    limit: int = 100,
    sort_by: str = "student_no",
    sort_direction: str = "asc",
    scope: dict[str, str] | list[dict[str, str]] | None = None,
) -> list[Student]:
    return list(db.scalars(build_student_query(keyword, current_class, school_major, college, school, filters, sort_by, sort_direction, scope).limit(min(limit, 500))))


def list_students_page(
    db: Session,
    keyword: str | None = None,
    current_class: str | None = None,
    school_major: str | None = None,
    college: str | None = None,
    school: str | None = None,
    filters: dict[str, str] | None = None,
    page: int = 1,
    page_size: int = 50,
    sort_by: str = "student_no",
    sort_direction: str = "asc",
    scope: dict[str, str] | list[dict[str, str]] | None = None,
) -> tuple[list[Student], int]:
    safe_page = max(1, page)
    safe_page_size = max(10, min(page_size, 100))
    statement = build_student_query(keyword, current_class, school_major, college, school, filters, sort_by, sort_direction, scope)
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = list(db.scalars(statement.offset((safe_page - 1) * safe_page_size).limit(safe_page_size)))
    return rows, total


def list_student_filter_options(
    db: Session,
    school: str | None = None,
    college: str | None = None,
    school_major: str | None = None,
    scope: dict[str, str] | list[dict[str, str]] | None = None,
) -> dict[str, list[str]]:
    """Build each cascade from the database, never from the current page of rows."""

    def values(field: str, **filters: str | None) -> list[str]:
        statement = build_student_query(
            school=filters.get("school"),
            college=filters.get("college"),
            school_major=filters.get("school_major"),
            scope=scope,
        )
        column = getattr(Student, field)
        return [
            str(value)
            for value in db.scalars(
                statement.with_only_columns(column, maintain_column_froms=True)
                .where(column.is_not(None), column != "")
                .distinct()
                .order_by(None)
                .order_by(column.asc())
            )
            if str(value).strip()
        ]

    hierarchy = {"school": school, "college": college, "school_major": school_major}
    return {
        "schools": values("school"),
        "colleges": values("college", school=hierarchy["school"]),
        "majors": values("school_major", school=hierarchy["school"], college=hierarchy["college"]),
        "classes": values("current_class", school=hierarchy["school"], college=hierarchy["college"], school_major=hierarchy["school_major"]),
        "political_statuses": values("political_status", school=hierarchy["school"], college=hierarchy["college"], school_major=hierarchy["school_major"]),
    }


def record_student_version(db: Session, student: Student, actor: User | None, changed_fields: list[str]) -> StudentVersion:
    version = StudentVersion(
        student_id=student.id,
        version_no=student.row_version,
        snapshot=student_to_dict(student),
        changed_fields=changed_fields,
        changed_by_id=actor.id if actor else None,
    )
    db.add(version)
    return version


def create_student(db: Session, payload: StudentCreate, actor: User | None = None) -> Student:
    if db.scalar(select(Student).where(Student.student_no == payload.student_no)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="学号已存在")
    student = Student(**payload.model_dump())
    db.add(student)
    db.flush()
    record_student_version(db, student, actor, list(STUDENT_FIELDS))
    return student


def update_student(db: Session, student: Student, payload: StudentUpdate, actor: User | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if student.row_version != payload.row_version:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="此记录已被其他人更新，请刷新后重试")
    before = student_to_dict(student)
    changes = payload.model_dump(exclude={"row_version"}, exclude_unset=True)
    for field, value in changes.items():
        setattr(student, field, value)
    student.row_version += 1
    db.flush()
    after = student_to_dict(student)
    record_student_version(db, student, actor, [field for field in changes if before.get(field) != after.get(field)])
    return before, after


def permanently_delete_student(db: Session, student: Student, actor: User | None = None) -> DeletedStudent:
    student_no = student.student_no
    cards = list(db.scalars(select(StudentRelatedInfoCard).where(StudentRelatedInfoCard.student_id == student.id)))
    deleted = DeletedStudent(
        original_student_id=student.id,
        student_no=student.student_no,
        full_name=student.full_name,
        snapshot=student_to_dict(student),
        related_cards=[{"source_document_id": card.source_document_id, "import_batch_id": card.import_batch_id, "imported_by_id": card.imported_by_id, "title": card.title, "excel_payload": card.excel_payload, "imported_at": card.imported_at.isoformat() if card.imported_at else None} for card in cards],
        deleted_by_id=actor.id if actor else None,
        expires_at=utcnow() + timedelta(days=max(1, get_settings().recycle_retention_days)),
    )
    db.add(deleted)
    db.execute(delete(FieldProvenance).where(FieldProvenance.student_id == student.id))
    db.execute(delete(RelatedInfoCandidate).where(RelatedInfoCandidate.student_id == student.id))
    db.execute(delete(StudentRelatedInfoCard).where(StudentRelatedInfoCard.student_id == student.id))
    db.execute(delete(StudentVersion).where(StudentVersion.student_id == student.id))
    for candidate in db.scalars(select(WordImportCandidate)):
        if str((candidate.candidate_data or {}).get("student_no") or "").strip() == student_no:
            db.delete(candidate)
    db.delete(student)
    db.flush()
    return deleted


def list_deleted_students(db: Session, include_restored: bool = False) -> list[DeletedStudent]:
    statement = select(DeletedStudent)
    if not include_restored:
        statement = statement.where(DeletedStudent.restored_at.is_(None))
    return list(db.scalars(statement.order_by(DeletedStudent.deleted_at.desc()).limit(500)))


def _snapshot_student_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = {field: snapshot.get(field) for field in STUDENT_FIELDS if field in snapshot}
    for field in DATE_FILTER_FIELDS:
        if isinstance(payload.get(field), str) and payload[field]:
            payload[field] = date.fromisoformat(payload[field])
    return payload


def restore_deleted_student(db: Session, record: DeletedStudent, actor: User | None = None) -> Student:
    if record.restored_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该回收站记录已恢复")
    if as_china_time(record.expires_at) < utcnow():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="该回收站记录已超过保留期")
    if db.scalar(select(Student).where(Student.student_no == record.student_no)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="当前已有相同学号，无法恢复")
    student = Student(**_snapshot_student_payload(record.snapshot or {}))
    db.add(student)
    db.flush()
    for item in record.related_cards or []:
        imported_at = item.get("imported_at")
        if isinstance(imported_at, str):
            imported_at = utcnow() if not imported_at else datetime.fromisoformat(imported_at)
        db.add(StudentRelatedInfoCard(student_id=student.id, source_document_id=item["source_document_id"], import_batch_id=item["import_batch_id"], imported_by_id=item["imported_by_id"], title=item["title"], excel_payload=item.get("excel_payload") or {}, imported_at=imported_at or utcnow()))
    record_student_version(db, student, actor, list(STUDENT_FIELDS))
    record.restored_at = utcnow()
    record.restored_by_id = actor.id if actor else None
    db.flush()
    return student


def list_student_versions(db: Session, student_id: int) -> list[StudentVersion]:
    return list(db.scalars(select(StudentVersion).where(StudentVersion.student_id == student_id).order_by(StudentVersion.version_no.desc(), StudentVersion.id.desc())))


def restore_student_version(db: Session, student: Student, version: StudentVersion, actor: User | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    before = student_to_dict(student)
    payload = _snapshot_student_payload(version.snapshot or {})
    for field, value in payload.items():
        if field != "student_no":
            setattr(student, field, value)
    student.row_version += 1
    db.flush()
    after = student_to_dict(student)
    record_student_version(db, student, actor, [field for field in STUDENT_FIELDS if before.get(field) != after.get(field)])
    return before, after


def purge_expired_deleted_students(db: Session) -> int:
    result = db.execute(delete(DeletedStudent).where(DeletedStudent.expires_at < utcnow(), DeletedStudent.restored_at.is_(None)))
    return result.rowcount or 0


def get_provenance(db: Session, student_id: int) -> list[FieldProvenance]:
    return list(
        db.scalars(
            select(FieldProvenance)
            .where(FieldProvenance.student_id == student_id)
            .order_by(FieldProvenance.recorded_at.desc())
        )
    )
