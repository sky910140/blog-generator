import os
from functools import lru_cache
from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    env: str = Field("local", description="Environment name")
    database_url: str = Field(
        "postgresql+psycopg2://postgres:postgres@localhost:5432/video2blog",
        description="PostgreSQL connection string",
    )
    static_dir: str = Field("static", description="Static files base directory")
    videos_dir_name: str = Field("videos", description="Directory name for videos under static")
    images_dir_name: str = Field("images", description="Directory name for images under static")
    max_video_minutes: int = Field(60, description="Max allowed video length in minutes")
    gemini_api_key: str | None = Field(None, description="Google Gemini API key")
    gemini_model: str = Field(
        "models/gemini-2.5-flash",
        description="Gemini model to use (e.g. models/gemini-2.5-flash, models/gemini-2.0-flash)",
    )
    ai_timeout_seconds: int = Field(300, description="Timeout for AI calls")
    ffmpeg_path: str = Field("ffmpeg", description="FFmpeg binary path")
    ffprobe_path: str = Field("ffprobe", description="FFprobe binary path")
    task_concurrency: int = Field(3, description="Max concurrent processing tasks")
    # Supabase Storage (for stateless deployments)
    supabase_url: str | None = Field(None, description="Supabase project URL, e.g. https://xxxx.supabase.co")
    supabase_service_role_key: str | None = Field(None, description="Supabase service role key for server-side uploads")
    supabase_storage_public_url: str | None = Field(None, description="Base public URL for Supabase storage (optional override)")
    supabase_bucket_videos: str = Field("videos", description="Supabase bucket name for videos")
    supabase_bucket_images: str = Field("images", description="Supabase bucket name for images")
    # Watermark removal (soft blur) settings for screenshots
    watermark_remove: bool = Field(False, description="Enable watermark blur on screenshots")
    watermark_width_ratio: float = Field(0.12, description="Watermark width ratio of frame (0-1)")
    watermark_height_ratio: float = Field(0.1, description="Watermark height ratio of frame (0-1)")
    watermark_x_ratio: float = Field(0.83, description="Watermark top-left X ratio (0-1, relative to frame width)")
    watermark_y_ratio: float = Field(0.85, description="Watermark top-left Y ratio (0-1, relative to frame height)")
    watermark_blur: int = Field(15, description="Blur strength for watermark region")
    # WeChat
    wechat_appid: str | None = Field(None, description="WeChat appid")
    wechat_secret: str | None = Field(None, description="WeChat secret")
    # Invite code gating
    invite_required: bool = Field(False, description="Whether invite code is required for creating tasks")
    invite_code: str | None = Field(None, description="Static invite code used when invite_required is true")
    invite_max_uses: int = Field(10, description="Max uses for default invite code")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


def ensure_directories(settings: Settings) -> None:
    os.makedirs(os.path.join(settings.static_dir, settings.videos_dir_name), exist_ok=True)
    os.makedirs(os.path.join(settings.static_dir, settings.images_dir_name), exist_ok=True)
