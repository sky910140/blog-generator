import io
import os
import uuid
from datetime import datetime
from typing import List

from fastapi import BackgroundTasks, Depends, FastAPI, File, HTTPException, UploadFile, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text

from .config import ensure_directories, get_settings
from .database import SessionLocal, engine, get_session
from .models import Base, Content, Project, ProjectStatus, InviteCode
from .schemas import ContentResponse, ContentUpdateRequest, ProjectCreateResponse, ProjectResponse
from .services.ai_engine import build_ai_engine
from .services.downloader import save_upload_file
from .services.markdown import build_markdown
from .services.media import capture_screenshot, get_video_duration_seconds
from .services.task_runner import TaskRunner
from .services.wechat import WeChatError, create_draft


class WechatDraftRequest(BaseModel):
    appid: str | None = None
    secret: str | None = None

settings = get_settings()
ensure_directories(settings)

app = FastAPI(title="Video2Blog Local")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")

task_runner = TaskRunner(max_workers=settings.task_concurrency)

# Initialize database schema (for quickstart; production should use Alembic)
Base.metadata.create_all(engine)
# Ensure invite_code column exists when running without migrations (PostgreSQL)
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE projects ADD COLUMN IF NOT EXISTS invite_code VARCHAR(64);"))


def _update_project(session: Session, project: Project, *, status_value: str | None = None, progress: int | None = None, error: str | None = None):
    if status_value:
        project.status = status_value
    if progress is not None:
        project.progress = progress
    if error is not None:
        project.error_msg = error
    project.updated_at = datetime.utcnow()
    session.add(project)
    session.commit()
    session.refresh(project)


def _process_project(project_id: uuid.UUID, video_path: str):
    session = SessionLocal()
    try:
        project: Project | None = session.get(Project, project_id)
        if not project:
            return

        _update_project(session, project, status_value=ProjectStatus.processing.value, progress=10)

        try:
            duration = get_video_duration_seconds(video_path, settings.ffprobe_path)
        except Exception as exc:
            _update_project(session, project, status_value=ProjectStatus.failed.value, error=str(exc), progress=100)
            return

        if duration > settings.max_video_minutes * 60:
            _update_project(
                session,
                project,
                status_value=ProjectStatus.failed.value,
                error=f"视频超过 {settings.max_video_minutes} 分钟限制",
                progress=100,
            )
            return

        project.duration = duration
        session.add(project)
        session.commit()

        ai_engine = build_ai_engine(settings.gemini_api_key, settings.ai_timeout_seconds, settings.gemini_model)
        try:
            ai_data = ai_engine.generate_steps(video_path, duration)
        except Exception as exc:
            _update_project(session, project, status_value=ProjectStatus.failed.value, error=str(exc), progress=100)
            return

        steps = ai_data.get("steps", [])
        # 生成标题（如有）
        headline = ai_data.get("headline")
        if headline:
            project.title = headline[:255]
            session.add(project)
            session.commit()
        _update_project(session, project, progress=60)

        image_base_dir = os.path.join(settings.static_dir, settings.images_dir_name)
        for step in steps:
            raw_ts = int(step.get("timestamp", 0))
            # Clamp timestamp to video duration range [0, duration-1]
            ts = max(0, min(raw_ts, max(duration - 1, 0)))
            step["timestamp"] = ts
            try:
                image_path = capture_screenshot(
                    video_path,
                    ts,
                    image_base_dir,
                    ffmpeg_path=settings.ffmpeg_path,
                    project_id=str(project.id),
                    watermark_remove=False,  # 保持原始清晰度，不做水印处理
                )
            except Exception as exc:
                _update_project(session, project, status_value=ProjectStatus.failed.value, error=str(exc), progress=100)
                return
            rel_image_path = f"/static/{settings.images_dir_name}/{os.path.basename(image_path)}"
            step["image_path"] = rel_image_path

        _update_project(session, project, progress=90)

        markdown = build_markdown(ai_data.get("summary"), steps)
        content = session.query(Content).filter(Content.project_id == project.id).one_or_none()
        if not content:
            content = Content(project_id=project.id)
        content.ai_raw_data = ai_data
        content.markdown_content = markdown
        content.updated_at = datetime.utcnow()
        session.add(content)
        session.commit()

        _update_project(session, project, status_value=ProjectStatus.completed.value, progress=100, error=None)
    finally:
        session.close()


@app.post("/api/projects/upload", response_model=ProjectCreateResponse)
async def upload_project(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    code = _consume_invite(request, db)
    video_dir = os.path.join(settings.static_dir, settings.videos_dir_name)
    video_path = save_upload_file(file, video_dir)
    rel_video_path = f"/static/{settings.videos_dir_name}/{os.path.basename(video_path)}"
    title = os.path.splitext(file.filename or "未命名视频")[0]

    project = Project(
        title=title,
        invite_code=code,
        source_type="local_file",
        local_video_path=rel_video_path,
        status=ProjectStatus.pending.value,
        progress=0,
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    # 提前创建空内容记录，避免前端轮询出现 404
    existing_content = db.query(Content).filter(Content.project_id == project.id).one_or_none()
    if not existing_content:
        placeholder = Content(project_id=project.id, ai_raw_data=None, markdown_content=None)
        db.add(placeholder)
        db.commit()

    background_tasks.add_task(task_runner.submit, str(project.id), _process_project, project.id, video_path)
    return ProjectCreateResponse(project_id=project.id, status=project.status)


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: uuid.UUID, request: Request, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    _require_project_access(request, db, project)
    return project


@app.get("/api/projects", response_model=List[ProjectResponse])
def list_projects(request: Request, db: Session = Depends(get_session)):
    if settings.invite_required:
        code = _consume_invite(request, db, consume=False)
        q = db.query(Project).filter(Project.invite_code == code).order_by(Project.created_at.desc())
    else:
        q = db.query(Project).order_by(Project.created_at.desc())
    projects = q.all()
    return projects


@app.get("/api/contents/{project_id}", response_model=ContentResponse)
def get_content(project_id: uuid.UUID, request: Request, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    _require_project_access(request, db, project)
    content = db.query(Content).filter(Content.project_id == project_id).one_or_none()
    if content:
        return content
    # 若不存在则创建占位记录
    placeholder = Content(project_id=project_id, ai_raw_data=None, markdown_content=None)
    db.add(placeholder)
    db.commit()
    db.refresh(placeholder)
    return placeholder


@app.put("/api/contents/{project_id}")
def update_content(project_id: uuid.UUID, payload: ContentUpdateRequest, request: Request, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    _require_project_access(request, db, project)
    content = db.query(Content).filter(Content.project_id == project_id).one_or_none()
    if not content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    content.markdown_content = payload.markdown
    content.updated_at = datetime.utcnow()
    db.add(content)
    db.commit()
    return {"success": True}


@app.get("/api/export/{project_id}")
def export_project(project_id: uuid.UUID, request: Request, db: Session = Depends(get_session)):
    project = db.get(Project, project_id)
    _require_project_access(request, db, project)
    content = db.query(Content).filter(Content.project_id == project_id).one_or_none()
    if not content or not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    import re
    memfile = io.BytesIO()
    import zipfile

    def safe_name(name: str) -> str:
        # Restrict to ASCII to avoid header encoding issues in Content-Disposition
        clean = re.sub(r"[^a-zA-Z0-9_-]+", "_", name).strip("_")
        return clean or "export"

    def resolve_path(path: str) -> str:
        rel = path.lstrip("/")
        if rel.startswith("static/"):
            rel = rel[len("static/") :]
        abs_path = os.path.join(settings.static_dir, rel)
        return abs_path

    with zipfile.ZipFile(memfile, "w", zipfile.ZIP_DEFLATED) as zf:
        md_name = f"{safe_name(project.title or 'export')}.md"
        zf.writestr(md_name, content.markdown_content or "")

        if content.ai_raw_data:
            for step in content.ai_raw_data.get("steps", []):
                path = step.get("image_path")
                if not path:
                    continue
                abs_path = resolve_path(path)
                if os.path.exists(abs_path):
                    try:
                        zf.write(abs_path, arcname=os.path.join("images", os.path.basename(abs_path)))
                    except FileNotFoundError:
                        # skip missing files to avoid export failure
                        continue
    memfile.seek(0)
    filename = f"{safe_name(project.title or 'export')}.zip"
    return StreamingResponse(
        memfile,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


def _get_invite_code_from_request(request: Request) -> str | None:
    return (
        request.headers.get("X-Invite-Code")
        or request.headers.get("x-invite-code")
        or request.query_params.get("invite_code")
    )


def _consume_invite(request: Request, db: Session, *, consume: bool = True) -> str | None:
    if not settings.invite_required:
        return None
    code = _get_invite_code_from_request(request)
    if not code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="邀请码无效或未提供")

    # 查找邀请码并锁定，防止并发超用
    invite = (
        db.query(InviteCode)
        .filter(InviteCode.code == code.strip(), InviteCode.active.is_(True))
        .with_for_update(nowait=False)
        .one_or_none()
    )

    # 若未事先创建，但配置了默认邀请码，自动落库
    if not invite and settings.invite_code and code.strip() == settings.invite_code.strip():
        invite = InviteCode(code=code.strip(), max_uses=settings.invite_max_uses)
        db.add(invite)
        db.commit()
        db.refresh(invite)

    if not invite:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="邀请码无效或已停用")
    if invite.used_count >= invite.max_uses:
        # 已用尽：读取类请求继续通过，消耗类请求（consume=True）阻止
        if consume:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="邀请码已用完")
        return invite.code

    if consume:
        invite.used_count += 1
        invite.updated_at = datetime.utcnow()
        db.add(invite)
        db.commit()
    return invite.code


def _require_project_access(request: Request, db: Session, project: Project | None) -> str | None:
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    if not settings.invite_required:
        return None
    code = _consume_invite(request, db, consume=False)
    # 严格隔离：项目邀请码必须匹配当前邀请码
    if project.invite_code != code:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return code


@app.post("/api/wechat/draft")
async def create_wechat_draft(
    project_id: uuid.UUID,
    request: Request,
    payload: WechatDraftRequest | None = None,
    db: Session = Depends(get_session),
):
    appid = (payload.appid if payload else None) or settings.wechat_appid
    secret = (payload.secret if payload else None) or settings.wechat_secret
    if not appid or not secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="需要提供 WECHAT_APPID/WECHAT_SECRET")
    project = db.get(Project, project_id)
    _require_project_access(request, db, project)
    content = db.query(Content).filter(Content.project_id == project_id).one_or_none()
    if not project or not content or not content.markdown_content:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")

    # 收集图片绝对路径
    image_paths = []
    if content.ai_raw_data:
        for step in content.ai_raw_data.get("steps", []):
            path = step.get("image_path")
            if path and path.startswith("/static/"):
                rel = path.lstrip("/")
                abs_path = os.path.join(settings.static_dir, rel[len("static/") :])
                if os.path.exists(abs_path):
                    image_paths.append(abs_path)

    try:
        media_id = await create_draft(
            project_title=project.title or "未命名",
            summary=content.ai_raw_data.get("summary") if content.ai_raw_data else "",
            markdown=content.markdown_content,
            image_paths=image_paths,
            appid=appid,
            secret=secret,
        )
        return {"success": True, "draft_media_id": media_id}
    except WeChatError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
