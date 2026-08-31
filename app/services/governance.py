"""Data-governance operations with explicit safety checks and traceability."""

from datetime import date, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.time import CHINA_TIMEZONE, as_china_time
from app.models import CandidateStatus, FieldProvenance, ImportBatch, ImportMatchReview, QualityIssueCase, RelatedInfoCandidate, Student, StudentMerge, StudentRelatedInfoCard, StudentVersion, User, WordImportCandidate, utcnow
from app.services.students import DATE_FILTER_FIELDS, STUDENT_FIELDS, record_student_version, student_to_dict


def _as_snapshot_payload(snapshot: dict[str, Any]) -> dict[str, Any]:
    payload = {field: snapshot.get(field) for field in STUDENT_FIELDS if field in snapshot}
    for field in DATE_FILTER_FIELDS:
        value = payload.get(field)
        if isinstance(value, str) and value:
            payload[field] = date.fromisoformat(value)
    return payload


def rollback_import_batch(db: Session, batch: ImportBatch, actor: User) -> dict[str, Any]:
    if batch.rollback_status != "available" or not isinstance(batch.rollback_data, dict):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该导入批次不可撤销，或已经撤销过")
    rollback_data = batch.rollback_data
    result: dict[str, Any] = {"removed": 0, "restored": 0, "blocked": []}

    for item in rollback_data.get("created", []):
        student = db.get(Student, int(item.get("student_id") or 0))
        if not student:
            continue
        if student.row_version != int(item.get("expected_row_version") or 0):
            result["blocked"].append({"student_no": student.student_no, "full_name": student.full_name, "reason": "导入后已被修改"})
            continue
        db.execute(delete(FieldProvenance).where(FieldProvenance.student_id == student.id))
        db.execute(delete(RelatedInfoCandidate).where(RelatedInfoCandidate.student_id == student.id))
        db.execute(delete(StudentRelatedInfoCard).where(StudentRelatedInfoCard.student_id == student.id))
        db.execute(delete(StudentVersion).where(StudentVersion.student_id == student.id))
        db.execute(delete(QualityIssueCase).where(QualityIssueCase.student_id == student.id))
        db.execute(delete(ImportMatchReview).where(ImportMatchReview.matched_student_id == student.id))
        db.delete(student)
        result["removed"] += 1

    for item in rollback_data.get("updated", []):
        student = db.get(Student, int(item.get("student_id") or 0))
        if not student:
            continue
        if student.row_version != int(item.get("expected_row_version") or 0):
            result["blocked"].append({"student_no": student.student_no, "full_name": student.full_name, "reason": "导入后已被修改"})
            continue
        before = student_to_dict(student)
        for field, value in _as_snapshot_payload(item.get("before") or {}).items():
            if field != "student_no":
                setattr(student, field, value)
        student.row_version += 1
        db.flush()
        record_student_version(db, student, actor, [str(field) for field in item.get("changed_fields") or []])
        db.execute(delete(FieldProvenance).where(FieldProvenance.import_batch_id == batch.id, FieldProvenance.student_id == student.id))
        result["restored"] += 1
        item["rollback_before"] = before

    batch.rollback_status = "partial" if result["blocked"] else "rolled_back"
    batch.rollback_data = rollback_data | {"rollback_result": result, "rolled_back_at": utcnow().isoformat(), "rolled_back_by_id": actor.id}
    db.flush()
    return result | {"status": batch.rollback_status}


def rollback_related_info_batch(db: Session, batch: ImportBatch, actor: User) -> dict[str, Any]:
    """Remove a related-information import without overwriting later manual notes."""
    if batch.mode != "related_info" or batch.rollback_status not in {None, "available"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="该学生相关信息导入不可撤销，或已经撤销过")

    rollback_data = dict(batch.rollback_data or {})
    changes = [item for item in rollback_data.get("related_changes") or [] if isinstance(item, dict)]
    changes_by_candidate = {int(item["candidate_id"]): item for item in changes if item.get("candidate_id")}
    result: dict[str, Any] = {"removed_candidates": 0, "removed_match_reviews": 0, "removed_cards": 0, "restored_remarks": 0, "blocked": []}
    candidates = list(db.scalars(select(RelatedInfoCandidate).where(RelatedInfoCandidate.import_batch_id == batch.id)))
    cards = list(db.scalars(select(StudentRelatedInfoCard).where(StudentRelatedInfoCard.import_batch_id == batch.id)))
    removable_candidate_ids: set[int] = set()
    reverted_student_ids: set[int] = set()

    for card in cards:
        student = db.get(Student, card.student_id)
        if student:
            student.row_version += 1
            db.flush()
            record_student_version(db, student, actor, ["remarks"])
            reverted_student_ids.add(student.id)
        db.delete(card)
        result["removed_cards"] += 1

    for candidate in candidates:
        if candidate.content_type == "excel_card" or candidate.status != CandidateStatus.APPROVED:
            removable_candidate_ids.add(candidate.id)
            continue
        change = changes_by_candidate.get(candidate.id)
        student = db.get(Student, candidate.student_id)
        if not change or not student:
            result["blocked"].append({"student_no": student.student_no if student else "-", "full_name": student.full_name if student else "已删除学生", "reason": "旧批次缺少备注快照，请手动处理"})
            continue
        if (student.remarks or "") != str(change.get("after_remarks") or ""):
            result["blocked"].append({"student_no": student.student_no, "full_name": student.full_name, "reason": "备注在导入后已被修改，未自动覆盖"})
            continue
        student.remarks = change.get("before_remarks") or None
        student.row_version += 1
        db.flush()
        record_student_version(db, student, actor, ["remarks"])
        reverted_student_ids.add(student.id)
        removable_candidate_ids.add(candidate.id)
        result["restored_remarks"] += 1

    for student_id in reverted_student_ids:
        db.execute(delete(FieldProvenance).where(FieldProvenance.import_batch_id == batch.id, FieldProvenance.student_id == student_id))
    for candidate in candidates:
        if candidate.id in removable_candidate_ids:
            db.delete(candidate)
            result["removed_candidates"] += 1
    reviews = list(db.scalars(select(ImportMatchReview).where(ImportMatchReview.import_batch_id == batch.id)))
    for review in reviews:
        db.delete(review)
        result["removed_match_reviews"] += 1

    batch.rollback_status = "partial" if result["blocked"] else "rolled_back"
    batch.rollback_data = rollback_data | {"rollback_result": result, "rolled_back_at": utcnow().isoformat(), "rolled_back_by_id": actor.id}
    db.flush()
    return result | {"status": batch.rollback_status}


def _duplicate_student_ref(student: Student) -> dict[str, Any]:
    return {
        "id": student.id,
        "student_no": student.student_no,
        "candidate_no": student.candidate_no,
        "full_name": student.full_name,
        "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
        "school": student.school,
        "college": student.college,
        "school_major": student.school_major,
        "current_class": student.current_class,
        "updated_at": student.updated_at,
    }


def list_duplicate_groups(db: Session, limit: int = 100) -> list[dict[str, Any]]:
    """Return explainable exact-match duplicate candidates for a human review."""
    students = list(db.scalars(select(Student).order_by(Student.updated_at.desc()).limit(10000)))
    buckets: dict[tuple[str, str], list[Student]] = {}
    for student in students:
        keys: list[tuple[str, str]] = []
        if student.national_id_hash:
            keys.append(("身份证号", f"hash:{student.national_id_hash}"))
        if student.candidate_no:
            keys.append(("考生号", f"candidate:{student.candidate_no.strip().lower()}"))
        if student.full_name and student.date_of_birth:
            keys.append(("姓名与出生日期", f"name-birth:{student.full_name.strip().lower()}:{student.date_of_birth.isoformat()}"))
        for key in keys:
            buckets.setdefault(key, []).append(student)
    groups = [
        {
            "match_type": kind,
            "count": len(rows),
            "students": [_duplicate_student_ref(student) for student in rows],
        }
        for (kind, _), rows in buckets.items()
        if len(rows) > 1
    ]
    groups.sort(key=lambda item: (-item["count"], item["match_type"], item["students"][0]["student_no"]))
    return groups[:max(1, min(limit, 200))]


def merge_students(db: Session, source: Student, target: Student, actor: User) -> dict[str, Any]:
    if source.id == target.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择两名不同的学生进行合并")
    source_snapshot = student_to_dict(source)
    target_before = student_to_dict(target)
    merged_fields: list[str] = []
    for field in STUDENT_FIELDS:
        if field in {"student_no", "full_name"}:
            continue
        source_value = getattr(source, field)
        target_value = getattr(target, field)
        if target_value in (None, "") and source_value not in (None, ""):
            setattr(target, field, source_value)
            merged_fields.append(field)
    if not target.full_name and source.full_name:
        target.full_name = source.full_name
        merged_fields.append("full_name")
    if merged_fields:
        target.row_version += 1
        db.flush()
        record_student_version(db, target, actor, merged_fields)

    target_provenance_keys = {
        (row.import_batch_id, row.field_name)
        for row in db.scalars(select(FieldProvenance).where(FieldProvenance.student_id == target.id))
    }
    for row in db.scalars(select(FieldProvenance).where(FieldProvenance.student_id == source.id)):
        if (row.import_batch_id, row.field_name) in target_provenance_keys:
            db.delete(row)
        else:
            row.student_id = target.id
            target_provenance_keys.add((row.import_batch_id, row.field_name))
    target_candidate_batches = {
        row.import_batch_id for row in db.scalars(select(RelatedInfoCandidate).where(RelatedInfoCandidate.student_id == target.id))
    }
    for candidate in db.scalars(select(RelatedInfoCandidate).where(RelatedInfoCandidate.student_id == source.id)):
        if candidate.import_batch_id in target_candidate_batches:
            db.delete(candidate)
        else:
            candidate.student_id = target.id
            target_candidate_batches.add(candidate.import_batch_id)
    for card in db.scalars(select(StudentRelatedInfoCard).where(StudentRelatedInfoCard.student_id == source.id)):
        card.student_id = target.id
    for review in db.scalars(select(ImportMatchReview).where(ImportMatchReview.matched_student_id == source.id)):
        review.matched_student_id = target.id
    target_issue_codes = {
        row.issue_code for row in db.scalars(select(QualityIssueCase).where(QualityIssueCase.student_id == target.id))
    }
    for issue in db.scalars(select(QualityIssueCase).where(QualityIssueCase.student_id == source.id)):
        if issue.issue_code in target_issue_codes:
            db.delete(issue)
        else:
            issue.student_id = target.id
            target_issue_codes.add(issue.issue_code)
    db.execute(delete(StudentVersion).where(StudentVersion.student_id == source.id))
    merge = StudentMerge(
        source_student_no=source.student_no,
        source_full_name=source.full_name,
        target_student_id=target.id,
        target_student_no=target.student_no,
        source_snapshot=source_snapshot,
        merged_fields=merged_fields,
        merged_by_id=actor.id,
    )
    db.add(merge)
    db.delete(source)
    db.flush()
    return {"merge_id": merge.id, "source": source_snapshot, "target_before": target_before, "target_after": student_to_dict(target), "merged_fields": merged_fields}


def student_timeline(db: Session, student: Student, limit: int = 120) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    user_ids: set[int] = set()
    versions = list(db.scalars(select(StudentVersion).where(StudentVersion.student_id == student.id).order_by(StudentVersion.created_at.desc()).limit(limit)))
    cards = list(db.scalars(select(StudentRelatedInfoCard).where(StudentRelatedInfoCard.student_id == student.id).order_by(StudentRelatedInfoCard.imported_at.desc()).limit(limit)))
    provenance = list(db.scalars(select(FieldProvenance).where(FieldProvenance.student_id == student.id).order_by(FieldProvenance.recorded_at.desc()).limit(limit)))
    user_ids.update(item.changed_by_id for item in versions if item.changed_by_id)
    user_ids.update(item.imported_by_id for item in cards if item.imported_by_id)
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_(user_ids)))} if user_ids else {}
    for version in versions:
        actor = users.get(version.changed_by_id)
        events.append({"type": "version", "title": "学生档案已更新", "detail": "、".join(version.changed_fields or []) or "完整快照", "at": version.created_at, "actor": (actor.display_name or actor.username) if actor else "系统"})
    for card in cards:
        actor = users.get(card.imported_by_id)
        events.append({"type": "related", "title": "学生相关信息词条已写入", "detail": card.title, "at": card.imported_at, "actor": (actor.display_name or actor.username) if actor else "系统"})
    for row in provenance:
        events.append({"type": "source", "title": "字段来源已记录", "detail": row.field_name, "at": row.recorded_at, "actor": "导入"})
    def timeline_time(value: datetime | None) -> datetime:
        return as_china_time(value) or datetime.min.replace(tzinfo=CHINA_TIMEZONE)

    events.sort(key=lambda item: timeline_time(item["at"]), reverse=True)
    for event in events:
        event["at"] = timeline_time(event["at"])
    return events[:limit]


def list_student_reminders(db: Session, scope: list[dict[str, str]] | None = None, limit: int = 100) -> list[dict[str, Any]]:
    from app.services.students import build_student_query

    students = list(db.scalars(build_student_query(scope=scope).order_by(None).limit(10000)))
    today = utcnow().date()
    stale_before = utcnow() - timedelta(days=max(1, get_settings().quality_stale_days))
    reminders: list[dict[str, Any]] = []
    for student in students:
        base = {"student_id": student.id, "student_no": student.student_no, "full_name": student.full_name, "school_major": student.school_major, "current_class": student.current_class}
        if not student.mobile_phone and not student.electronic_email:
            reminders.append(base | {"code": "missing_contact", "severity": "medium", "title": "缺少联系方式", "detail": "未填写手机号码和电子邮箱"})
        if student.archive_transferred in (None, "", "否"):
            reminders.append(base | {"code": "archive_transfer", "severity": "low", "title": "档案转入待核对", "detail": "档案是否转入学校尚未确认或标记为否"})
        if student.graduation_date and 0 <= (student.graduation_date - today).days <= 120:
            reminders.append(base | {"code": "graduation_due", "severity": "medium", "title": "毕业日期临近", "detail": f"毕业日期：{student.graduation_date.isoformat()}"})
        updated_at = as_china_time(student.updated_at)
        if updated_at and updated_at < stale_before:
            reminders.append(base | {"code": "stale_profile", "severity": "low", "title": "档案长期未更新", "detail": f"最近更新：{updated_at:%Y-%m-%d}"})
    order = {"high": 0, "medium": 1, "low": 2}
    reminders.sort(key=lambda item: (order.get(item["severity"], 9), item["student_no"], item["code"]))
    return reminders[:max(1, min(limit, 300))]
