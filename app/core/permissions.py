from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db import get_db
from app.models import Role, User


CAPABILITIES = frozenset({"student_edit", "student_export", "related_review", "source_manage", "quality_manage", "audit_view"})
DEFAULT_CAPABILITIES = {
    Role.SUPER_ADMIN: CAPABILITIES,
    Role.ADMIN: CAPABILITIES,
    Role.TEACHER: frozenset({"student_edit", "student_export", "related_review"}),
}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:] if authorization.lower().startswith("bearer ") else request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    payload = decode_access_token(token)
    user_id = payload.get("sub")
    if not user_id or not str(user_id).isdigit():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效会话")
    user = db.get(User, int(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号不可用")
    if int(payload.get("sv") or 0) != max(1, int(user.session_version or 1)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已被注销，请重新登录")
    if user.must_change_password and request.url.path not in {"/api/me", "/api/auth/password", "/api/auth/logout", "/api/auth/mfa/setup", "/api/auth/mfa/enable", "/api/auth/mfa/disable"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="该账号需要先更新初始密码")
    return user


def require_roles(*roles: Role) -> Callable:
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有此操作权限")
        return user

    return checker


def may_edit(user: User) -> bool:
    return has_capability(user, "student_edit")


def user_capabilities(user: User) -> list[str]:
    if user.role == Role.SUPER_ADMIN:
        return sorted(CAPABILITIES)
    configured = user.permissions
    allowed = DEFAULT_CAPABILITIES[user.role] if configured is None else frozenset(str(item) for item in configured if str(item) in CAPABILITIES)
    return sorted(allowed)


def has_capability(user: User, capability: str) -> bool:
    return capability in user_capabilities(user)
