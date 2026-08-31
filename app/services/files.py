import hashlib
import re
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import SourceDocument, User

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".xlsx": "excel", ".docx": "word"}


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._\-()\u4e00-\u9fff]", "_", name)[:180] or "upload"


async def register_upload(db: Session, upload: UploadFile, actor: User) -> tuple[SourceDocument, bytes]:
    filename = safe_filename(upload.filename or "upload")
    extension = Path(filename).suffix.lower()
    file_type = ALLOWED_EXTENSIONS.get(extension)
    if not file_type:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 .xlsx 和 .docx 文件")

    content = await upload.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件不得超过 25 MB")

    sha256 = hashlib.sha256(content).hexdigest()
    version_group = hashlib.sha256(filename.lower().encode("utf-8")).hexdigest()[:32]
    latest_version = db.scalar(select(func.max(SourceDocument.version_no)).where(SourceDocument.version_group == version_group)) or 0
    settings = get_settings()
    folder = settings.storage_path / file_type
    folder.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex}_{sha256[:12]}{extension}"
    (folder / stored_name).write_bytes(content)

    document = SourceDocument(
        original_filename=filename,
        stored_filename=str(Path(file_type) / stored_name),
        file_type=file_type,
        mime_type=upload.content_type,
        sha256=sha256,
        size_bytes=len(content),
        version_group=version_group,
        version_no=latest_version + 1,
        tags=[],
        status="active",
        uploaded_by_id=actor.id,
    )
    db.add(document)
    db.flush()
    return document, content


def document_path(document: SourceDocument) -> Path:
    root = get_settings().storage_path.resolve()
    target = (root / document.stored_filename).resolve()
    if root not in target.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="原始文件路径无效")
    return target
