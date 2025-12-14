import os
import subprocess
import uuid
import tempfile
from typing import List

from .storage import SupabaseStorageClient


def get_video_duration_seconds(video_path: str, ffprobe_path: str = "ffprobe") -> int:
    """Return duration in seconds using ffprobe."""
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    try:
        return int(float(result.stdout.strip()))
    except ValueError as exc:
        raise RuntimeError("Unable to parse video duration") from exc


def get_video_resolution(video_path: str, ffprobe_path: str = "ffprobe") -> tuple[int, int]:
    """Return (width, height) using ffprobe."""
    cmd = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height",
        "-of",
        "csv=s=x:p=0",
        video_path,
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    try:
        width_str, height_str = result.stdout.strip().split("x")
        return int(width_str), int(height_str)
    except Exception as exc:
        raise RuntimeError("Unable to parse video resolution") from exc


def capture_screenshot(
    video_path: str,
    timestamp: int,
    storage: SupabaseStorageClient,
    bucket: str,
    ffmpeg_path: str = "ffmpeg",
    project_id: str | None = None,
    watermark_remove: bool = False,
    wm_w_ratio: float = 0.2,
    wm_h_ratio: float = 0.15,
    wm_x_ratio: float = 0.8,
    wm_y_ratio: float = 0.85,
    wm_blur: int = 20,
) -> str:
    """Capture a frame, upload to Supabase, return public URL."""
    tmp_dir = tempfile.mkdtemp()
    unique = uuid.uuid4().hex
    prefix = f"{project_id}_" if project_id else ""
    filename = f"{prefix}{timestamp}_{unique}.jpg"
    output_path = os.path.join(tmp_dir, filename)

    filters: list[str] = []
    if watermark_remove:
        try:
            width, height = get_video_resolution(video_path, ffprobe_path=ffmpeg_path.replace("ffmpeg", "ffprobe"))
            wm_w = max(4, int(width * wm_w_ratio))
            wm_h = max(4, int(height * wm_h_ratio))
            wm_x = int(width * wm_x_ratio)
            wm_y = int(height * wm_y_ratio)
            wm_x = max(0, min(wm_x, width - wm_w))
            wm_y = max(0, min(wm_y, height - wm_h))
            if wm_x + wm_w > width or wm_y + wm_h > height:
                raise ValueError("watermark ROI invalid")
            filters.append(
                f"split[a][b];"
                f"[b]crop={wm_w}:{wm_h}:{wm_x}:{wm_y},"
                f"boxblur={wm_blur}[wm];"
                f"[a][wm]overlay={wm_x}:{wm_y}"
            )
        except Exception:
            pass
    filter_str = ",".join(filters) if filters else None

    cmd = [
        ffmpeg_path,
        "-ss",
        str(timestamp),
        "-i",
        video_path,
        "-frames:v",
        "1",
        "-q:v",
        "2",
    ]
    if filter_str:
        cmd.extend(["-vf", filter_str])
    cmd.extend([output_path, "-y"])
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr}")

    remote_url = storage.upload_file(bucket, output_path, filename)
    try:
        os.remove(output_path)
    except OSError:
        pass
    return remote_url


def batch_capture_screenshots(
    video_path: str,
    timestamps: List[int],
    storage: SupabaseStorageClient,
    bucket: str,
    ffmpeg_path: str = "ffmpeg",
    project_id: str | None = None,
) -> List[str]:
    """Capture multiple frames; returns list of URLs."""
    images = []
    for ts in timestamps:
        images.append(
            capture_screenshot(
                video_path,
                ts,
                storage=storage,
                bucket=bucket,
                ffmpeg_path=ffmpeg_path,
                project_id=project_id,
            )
        )
    return images
