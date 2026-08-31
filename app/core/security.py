import base64
import base64
import hashlib
import hmac
import secrets
import struct
import time
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

password_context = CryptContext(schemes=["argon2"], deprecated="auto")
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return password_context.verify(password, password_hash)


def create_access_token(user_id: int, role: str, session_version: int = 1) -> str:
    settings = get_settings()
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    return jwt.encode({"sub": str(user_id), "role": role, "sv": max(1, int(session_version)), "exp": expires}, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, get_settings().jwt_secret, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="会话已失效，请重新登录") from exc


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def new_totp_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _totp_code(secret: str, counter: int) -> str:
    normalized = secret.strip().upper()
    padding = "=" * (-len(normalized) % 8)
    key = base64.b32decode(normalized + padding, casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
    return f"{value:06d}"


def verify_totp_code(secret: str | None, code: str | None, timestamp: int | None = None) -> bool:
    if not secret or not code or not str(code).strip().isdigit() or len(str(code).strip()) != 6:
        return False
    counter = int((timestamp if timestamp is not None else time.time()) // 30)
    supplied = str(code).strip()
    try:
        return any(hmac.compare_digest(_totp_code(secret, counter + offset), supplied) for offset in (-1, 0, 1))
    except (ValueError, base64.binascii.Error):
        return False


def require_csrf(request: Request) -> None:
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        return
    header_token = request.headers.get("X-CSRF-Token")
    cookie_token = request.cookies.get("csrf_token")
    if not header_token or not cookie_token or not secrets.compare_digest(header_token, cookie_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")
