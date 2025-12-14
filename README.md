# Video2Blog Local (MVP)

本仓库实现《视频转图文教程生成器 (Video2Blog Local)》的最小可运行版本，满足 PRD/SDD 中的核心流程：本地上传视频（< 30 分钟）→ 后台生成步骤+截图 → Markdown 编辑 → 导出 MD+图片包。

## 目录结构
- `backend/` FastAPI 后端，PostgreSQL 持久化
  - `main.py` 路由与任务编排，挂载静态资源
  - `models.py`/`schemas.py`/`config.py`/`database.py`
  - `services/` 下载保存、AI 占位实现、FFmpeg 截图、Markdown 生成、轻量任务池
- `static/` 静态资源目录（视频与截图）
- `frontend/` Next.js 14 App Router 前端
  - 仪表盘 + 任务轮询
  - 详情页：Markdown 编辑 + 视频联动预览 + 导出

## 运行后端
```bash
python -m venv .venv && source .venv/bin/activate  # Windows 使用 .venv\\Scripts\\activate
pip install -r backend/requirements.txt

# 配置环境变量（可在 backend/.env 中设置）
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/video2blog"
export GEMINI_API_KEY="your-key-if-available"
export GEMINI_MODEL="gemini-1.5-flash-001"  # 可选，默认 flash
# 微信草稿推送（可选）
# export WECHAT_APPID="your-appid"
# export WECHAT_SECRET="your-secret"

uvicorn backend.main:app --reload --port 8000
```

> 默认会自动 `create_all` 建表；生产环境请使用 Alembic 迁移。

## 运行前端
```bash
cd frontend
npm install
npm run dev  # http://localhost:3000
```

如后端端口非 8000，请设置 `NEXT_PUBLIC_API_BASE=http://localhost:8000`（前端访问后端静态资源与 API 都通过该地址）。

## 关键行为
- 上传：仅支持 MP4/MOV，本地保存至 `static/videos/`，记录为 `projects` 状态 `pending`。
- 处理：后台任务切换为 `processing` → 运行 Gemini（有 Key 时）生成步骤；无 Key 时回退占位逻辑 → FFmpeg 截图（1280x720, JPEG 质量 3）保存到 `static/images/{projectId}_{ts}_{uuid}.jpg` → 生成 Markdown → 状态 `completed`。
- 失败：任何异常会写入 `error_msg` 并标记 `failed`。
- 导出：打包 Markdown + 生成的图片为 ZIP。
- 微信草稿推送：配置好 `WECHAT_APPID/SECRET` 后，可调用 `POST /api/wechat/draft?project_id=...` 将 Markdown/图片转换为公众号草稿（需微信外网可访问）。

## TODO / 扩展
- 将 `services/ai_engine.py` 中的占位逻辑替换为真实 Gemini 视频输入调用（含长视频抽帧/降级策略）。
- 补充 Alembic 迁移脚本与生产配置（CORS 白名单、鉴权、限流）。
- 前端补充重新截图/自定义图片上传入口，对接相应后端 API。
- 增加任务重试接口、更多错误码与日志。
