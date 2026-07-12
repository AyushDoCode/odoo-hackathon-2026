from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.deps import get_current_user
from app.modules.users.models import User

router = APIRouter(prefix="/files", tags=["files"])

_ALLOWED_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/pdf": ".pdf",
}


def _upload_root() -> Path:
    root = Path(settings.upload_directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    _current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    suffix = _ALLOWED_TYPES.get(file.content_type or "")
    if suffix is None:
        raise HTTPException(415, "Only JPEG, PNG, and PDF files are supported")
    content = await file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(413, "File exceeds the configured upload limit")
    if not content:
        raise HTTPException(400, "File is empty")

    filename = f"{uuid4().hex}{suffix}"
    (_upload_root() / filename).write_bytes(content)
    return {"url": f"/files/{filename}"}


@router.get("/{filename}")
async def download_file(
    filename: str,
    _current_user: User = Depends(get_current_user),
) -> FileResponse:
    if Path(filename).name != filename:
        raise HTTPException(404, "File not found")
    path = _upload_root() / filename
    if not path.is_file():
        raise HTTPException(404, "File not found")
    return FileResponse(path)
