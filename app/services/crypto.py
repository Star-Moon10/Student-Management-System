import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import Text, TypeDecorator

from app.core.config import get_settings


def _key() -> bytes:
    configured = (get_settings().data_encryption_key or "").strip()
    if configured:
        try:
            Fernet(configured.encode("ascii"))
            return configured.encode("ascii")
        except (ValueError, TypeError) as exc:
            raise RuntimeError("DATA_ENCRYPTION_KEY 不是有效的 Fernet 密钥") from exc
    return base64.urlsafe_b64encode(hashlib.sha256(get_settings().jwt_secret.encode("utf-8")).digest())


def cipher() -> Fernet:
    return Fernet(_key())


def encrypt_text(value: str) -> str:
    return cipher().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_text(value: str) -> str:
    try:
        return cipher().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeEncodeError):
        # Legacy plaintext is returned during the automatic migration only.
        return value


def encrypt_bytes(value: bytes) -> bytes:
    return cipher().encrypt(value)


def decrypt_bytes(value: bytes) -> bytes:
    try:
        return cipher().decrypt(value)
    except InvalidToken as exc:
        raise RuntimeError("备份包无法解密，请确认 DATA_ENCRYPTION_KEY 未变更") from exc


def blind_index(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    key = hashlib.sha256(_key()).digest()
    return hmac.new(key, text.lower().encode("utf-8"), hashlib.sha256).hexdigest()


class EncryptedText(TypeDecorator[str]):
    """Encrypted-at-rest text with legacy plaintext compatibility during migration."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect):
        if value is None or value == "":
            return value
        text = str(value)
        if text.startswith("gAAAA"):
            return text
        return encrypt_text(text)

    def process_result_value(self, value: str | None, dialect):
        if value is None or value == "":
            return value
        return decrypt_text(str(value))


class EncryptedJSON(TypeDecorator[Any]):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect):
        if value is None:
            return None
        if isinstance(value, str) and value.startswith("gAAAA"):
            return value
        return encrypt_text(json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":")))

    def process_result_value(self, value: str | None, dialect):
        if value is None:
            return None
        raw = decrypt_text(str(value))
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
