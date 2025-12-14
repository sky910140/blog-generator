import os
import re
import uuid
import tempfile
from fastapi import UploadFile, HTTPException, status

from .storage import SupabaseStorageClient

ALLOWED_EXTENSIONS = {".mp4", ".mov"}


def _safe_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
    if not safe_name:
        safe_name = "video"
    return safe_name + ext.lower()


def save_upload_file(upload_file: UploadFile, storage: SupabaseStorageClient, bucket: str) -> tuple[str, str]:
    """
    Save upload to temp file (for ffprobe/ffmpeg) and upload to Supabase Storage.
    Returns (local_temp_path, public_url).
    """
    _, ext = os.path.splitext(upload_file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"仅支持MP4/MOV，收到了{ext or '未知类型'}",
        )
    filename = _safe_filename(upload_file.filename or f"video{ext}")
    unique_name = f"{uuid.uuid4().hex}_{filename}"

    fd, tmp_path = tempfile.mkstemp(suffix=ext)
    with os.fdopen(fd, "wb") as out_file:
        upload_file.file.seek(0)
        out_file.write(upload_file.file.read())

    remote_url = storage.upload_file(bucket, tmp_path, unique_name)
    return tmp_path, remote_url
