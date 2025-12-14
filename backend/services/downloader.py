import os
import re
import shutil
import uuid
from fastapi import UploadFile, HTTPException, status


ALLOWED_EXTENSIONS = {".mp4", ".mov"}


def _safe_filename(filename: str) -> str:
    name, ext = os.path.splitext(filename)
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
    if not safe_name:
        safe_name = "video"
    return safe_name + ext.lower()


def save_upload_file(upload_file: UploadFile, dest_dir: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    _, ext = os.path.splitext(upload_file.filename or "")
    ext = ext.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"仅支持 MP4/MOV，收到 {ext or '未知类型'}",
        )
    filename = _safe_filename(upload_file.filename or f"video{ext}")
    unique_name = f"{uuid.uuid4().hex}_{filename}"
    target_path = os.path.join(dest_dir, unique_name)

    with open(target_path, "wb") as out_file:
        shutil.copyfileobj(upload_file.file, out_file)

    return target_path
