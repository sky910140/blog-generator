# Video2Blog Local

将本地视频（<60 分钟）转成带截图的 Markdown 教程，并可推送公众号草稿。后端基于 FastAPI+PostgreSQL，前端基于 Next.js 14。

## 功能概览
- 上传 MP4/MOV 本地视频，记录为 `projects`，并存储到 `static/videos/`
- AI 步骤生成：调用 Gemini（无 Key 时使用占位/FFmpeg 截图 fallback），生成步骤+摘要
- 截图：FFmpeg 截帧，存储到 `static/images/`
- Markdown 在线编辑与导出 ZIP（Markdown + 图片）
- 邀请码访问控制，支持同一码多项目查询
- 公众号草稿推送（需配置 AppID/Secret 与 IP 白名单）

## 目录结构
- `backend/` FastAPI & 数据层
  - `main.py` 路由与任务调度，挂载静态资源
  - `models.py`/`schemas.py`/`config.py`/`database.py`
  - `services/` AI 调用、下载保存、FFmpeg 截图、Markdown 生成、任务池、公众号推送
- `static/` 静态资源（视频与截图）
- `frontend/` Next.js 14 App Router
  - 仪表盘 + 轮询任务
  - 详情页：Markdown 编辑 + 视频联动预览 + 导出 + 公众号草稿推送

## 环境要求
- Python 3.11+，Node.js 18+
- PostgreSQL 实例可访问
- FFmpeg/FFprobe 安装并在 PATH 或 `.env` 中配置绝对路径
- （可选）Gemini API Key，用于真实步骤生成

## 快速启动
### 后端
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# 配置环境变量（或在 .env 中设置）
export DATABASE_URL="postgresql+psycopg2://postgres:postgres@localhost:5432/video2blog"
export GEMINI_API_KEY="your-gemini-key"             # 可选，无则使用占位
export GEMINI_MODEL="models/gemini-2.5-flash"       # 可选，默认 2.5-flash
export FFMPEG_PATH="/usr/bin/ffmpeg"                # Windows 配置绝对路径
export FFPROBE_PATH="/usr/bin/ffprobe"
# 公众号草稿（可选）
# export WECHAT_APPID="your-appid"
# export WECHAT_SECRET="your-secret"

uvicorn backend.main:app --reload --port 8000
```
> 后端会自动 `create_all` 创建表；生产环境建议使用 Alembic 迁移。

### 前端
```bash
cd frontend
npm install
npm run dev  # 默认 http://localhost:3000
```
> 若后端端口非 8000，设置 `NEXT_PUBLIC_API_BASE=http://localhost:8000`。

## 配置项（`.env` 示例）
```env
DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/video2blog
GEMINI_API_KEY=your-gemini-key
GEMINI_MODEL=models/gemini-2.5-flash
AI_TIMEOUT_SECONDS=300
STATIC_DIR=static
VIDEOS_DIR_NAME=videos
IMAGES_DIR_NAME=images
FFMPEG_PATH=C:\path\to\ffmpeg.exe
FFPROBE_PATH=C:\path\to\ffprobe.exe
MAX_VIDEO_MINUTES=60
INVITE_REQUIRED=true
INVITE_CODE=your-code
INVITE_MAX_USES=10
WECHAT_APPID=your-appid
WECHAT_SECRET=your-secret
```

## 使用流程
1) 在首页输入邀请码（如启用），通过后显示任务列表；上传本地视频生成新项目。
2) 后端处理：获取时长 -> AI 步骤生成 -> FFmpeg 截图 -> 拼接 Markdown -> 状态 `completed`。
3) 详情页：可编辑 Markdown、导出 ZIP；填写 AppID/Secret 可推送公众号草稿（需将服务器 IP 加入公众号 API 白名单）。
4) 若无 Gemini Key 或调用失败，使用占位步骤与截图 fallback（可在日志中确认）。

## 邀请码策略
- `INVITE_REQUIRED=true` 时，创建/访问项目均需邀请码；同一码下的项目可查询，即使次数已用尽也允许查看历史。
- `INVITE_MAX_USES` 控制最大使用次数，超出后仅阻止新建/消耗类操作。

## 常见问题
- **乱码/占位内容**：确认已配置有效 `GEMINI_API_KEY` 且服务器可访问外网；查看后端日志是否出现 “using synthetic steps”。
- **FFmpeg 未找到**：配置 `FFMPEG_PATH/FFPROBE_PATH` 为绝对路径并重启后端。
- **公众号推送失败**：确认 AppID/Secret 正确、服务器 IP 在公众号 API 白名单内。
- **端口调整**：前端通过 `NEXT_PUBLIC_API_BASE` 指向后端，后端通过 `--port` 指定监听端口。

## 待办/扩展
- 将 AI 占位逻辑替换为真实多模型回退策略，支持长视频分段/抽帧降级
- 补充 Alembic 迁移与生产级配置（CORS、鉴权、限流）
- 前端补充重试/自定义截图上传入口，对接对应后端 API
- 增加任务重试接口、更丰富的错误码与日志
