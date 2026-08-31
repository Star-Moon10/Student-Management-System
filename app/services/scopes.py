from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.models import Role, Student, User, UserDataScope, UserDataScopeRule
SCOPE_FIELDS = ("school", "college", "school_major", "current_class")


def get_user_scope(db: Session, user: User) -> UserDataScope | None:
    return db.scalar(select(UserDataScope).where(UserDataScope.user_id == user.id))


def get_user_scopes(db: Session, user: User) -> list[dict[str, str]]:
    legacy = scope_as_dict(get_user_scope(db, user))
    rules = [scope_as_dict(rule) for rule in db.scalars(select(UserDataScopeRule).where(UserDataScopeRule.user_id == user.id).order_by(UserDataScopeRule.id.asc()))]
    values = [item for item in [legacy, *rules] if item]
    return list({tuple(sorted(item.items())): item for item in values}.values())


def get_effective_user_scopes(db: Session, user: User) -> list[dict[str, str]]:
    """An empty scope is the explicit all-students scope used by the UI."""
    return get_user_scopes(db, user)


def scope_as_dict(scope: UserDataScope | None) -> dict[str, str]:
    if not scope:
        return {}
    return {field: str(getattr(scope, field) or "") for field in SCOPE_FIELDS if getattr(scope, field)}


def apply_scope(statement: Select[Any], db: Session, user: User) -> Select[Any]:
    if user.role == Role.SUPER_ADMIN:
        return statement
    scopes = get_effective_user_scopes(db, user)
    if scopes:
        return statement.where(or_(*(and_(*(getattr(Student, field) == value for field, value in item.items())) for item in scopes)))
    return statement


def ensure_student_scope(db: Session, user: User, student: Student) -> None:
    if user.role == Role.SUPER_ADMIN:
        return
    scopes = get_effective_user_scopes(db, user)
    if scopes and not any(all(getattr(student, field) == value for field, value in item.items()) for item in scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该学生不在您的数据权限范围内")


def ensure_new_student_scope(db: Session, user: User, payload: dict[str, Any]) -> None:
    if user.role == Role.SUPER_ADMIN:
        return
    scopes = get_effective_user_scopes(db, user)
    if scopes and not any(all(str(payload.get(field) or "") == value for field, value in item.items()) for item in scopes):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="新增数据必须属于您的数据权限范围")


def serialize_student_for_user(db: Session, user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """Data scope controls visibility; student fields are never role-masked."""
    return payload
