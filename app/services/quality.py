import re
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import as_china_time
from app.models import QualityIssueCase, QualityScan, Student, User, utcnow


PHONE_PATTERN = re.compile(r"^1[3-9]\d{9}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _student_ref(student: Student) -> dict[str, Any]:
    return {"id": student.id, "student_no": student.student_no, "full_name": student.full_name, "college": student.college, "school_major": student.school_major, "current_class": student.current_class}


def run_quality_scan(db: Session, actor: User | None = None) -> QualityScan:
    students = list(db.scalars(select(Student).order_by(Student.id.asc())))
    issues: list[dict[str, Any]] = []
    issue_rows: dict[str, list[dict[str, Any]]] = {}

    missing = [_student_ref(row) for row in students if not row.student_no or not row.full_name]
    profile_missing = [
        _student_ref(row)
        for row in students
        if any(not getattr(row, field) for field in ("school", "college", "school_major", "current_class"))
    ]
    contacts = [_student_ref(row) for row in students if not row.mobile_phone and not row.electronic_email]
    phones = [_student_ref(row) for row in students if row.mobile_phone and not PHONE_PATTERN.fullmatch(str(row.mobile_phone).replace(" ", "").replace("-", ""))]
    emails = [_student_ref(row) for row in students if row.electronic_email and not EMAIL_PATTERN.fullmatch(str(row.electronic_email).strip())]
    stale_cutoff = utcnow() - timedelta(days=max(1, get_settings().quality_stale_days))
    stale = [_student_ref(row) for row in students if row.updated_at and as_china_time(row.updated_at) < stale_cutoff]
    today = utcnow().date()
    invalid_dates = [
        _student_ref(row)
        for row in students
        if (row.date_of_birth and (row.date_of_birth > today or row.date_of_birth.year < 1900))
        or (row.enrollment_date and row.graduation_date and row.enrollment_date > row.graduation_date)
    ]
    for code, label, severity, rows in (
        ("required", "缺少学号或姓名", "high", missing),
        ("profile", "学校、学院、专业或班级不完整", "medium", profile_missing),
        ("contact", "未留手机或电子邮箱", "medium", contacts),
        ("phone", "手机号码格式异常", "medium", phones),
        ("email", "电子邮箱格式异常", "medium", emails),
        ("stale", "超过设定期限未更新", "low", stale),
        ("date", "出生、入学或毕业日期异常", "medium", invalid_dates),
    ):
        issue_rows[code] = rows
        issues.append({"code": code, "label": label, "severity": severity, "count": len(rows), "students": rows[:100]})

    # Encrypted identifiers are randomized at rest; their blind index is the
    # searchable value used for duplicate detection.
    duplicates = list(
        db.execute(
            select(Student.national_id_hash, func.count(Student.id))
            .where(Student.national_id_hash.is_not(None), Student.national_id_hash != "")
            .group_by(Student.national_id_hash)
            .having(func.count(Student.id) > 1)
        )
    )
    duplicate_rows: list[dict[str, Any]] = []
    for national_id_hash, _count in duplicates:
        duplicate_rows.extend(_student_ref(row) for row in db.scalars(select(Student).where(Student.national_id_hash == national_id_hash)))
    issue_rows["duplicate_national_id"] = duplicate_rows
    issues.append({"code": "duplicate_national_id", "label": "身份证号重复", "severity": "high", "count": len(duplicate_rows), "students": duplicate_rows[:100]})
    existing_cases = {(case.issue_code, case.student_id): case for case in db.scalars(select(QualityIssueCase))}
    active_keys: set[tuple[str, int]] = set()
    for code, rows in issue_rows.items():
        for row in rows:
            key = (code, row["id"])
            active_keys.add(key)
            case = existing_cases.get(key)
            if case is None:
                case = QualityIssueCase(issue_code=code, student_id=row["id"], status="open")
                db.add(case)
                existing_cases[key] = case
            elif case.status == "resolved":
                case.status = "open"
                case.resolved_at = None
            case.last_seen_at = utcnow()
    for key, case in existing_cases.items():
        if key not in active_keys and case.status == "open":
            case.status = "resolved"
            case.resolution_note = "后续质量扫描未再发现该问题"
            case.resolved_at = utcnow()
    db.flush()
    cases = {(case.issue_code, case.student_id): case for case in db.scalars(select(QualityIssueCase))}
    for issue in issues:
        for student in issue["students"]:
            case = cases.get((issue["code"], student["id"]))
            if case:
                student["case_id"] = case.id
                student["case_status"] = case.status
                student["assignee_id"] = case.assignee_id
    summary = {item["code"]: item["count"] for item in issues} | {"total_students": len(students), "total_issues": sum(item["count"] for item in issues)}
    scan = QualityScan(requested_by_id=actor.id if actor else None, summary=summary, issues=issues)
    db.add(scan)
    db.flush()
    return scan


def serialize_quality_scan(scan: QualityScan) -> dict[str, Any]:
    return {"id": scan.id, "summary": scan.summary or {}, "issues": scan.issues or [], "created_at": scan.created_at}
