import os
import time
from typing import Dict, List, Tuple

import httpx
import json

from ..config import get_settings

settings = get_settings()

_cached_token: Tuple[str, float] | None = None  # (token, expire_ts)


class WeChatError(Exception):
    pass


async def get_access_token() -> str:
    global _cached_token
    if _cached_token and _cached_token[1] > time.time() + 60:
        return _cached_token[0]
    if not settings.wechat_appid or not settings.wechat_secret:
        raise WeChatError("WECHAT_APPID 或 WECHAT_SECRET 未配置")
    url = "https://api.weixin.qq.com/cgi-bin/token"
    params = {
        "grant_type": "client_credential",
        "appid": settings.wechat_appid,
        "secret": settings.wechat_secret,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, params=params)
        data = resp.json()
    if "access_token" not in data:
        raise WeChatError(f"获取 access_token 失败: {data}")
    token = data["access_token"]
    expire = time.time() + int(data.get("expires_in", 7200))
    _cached_token = (token, expire)
    return token


async def upload_image(abs_path: str) -> Tuple[str, str]:
    """
    上传图片素材，返回 (media_id, url)。
    """
    token = await get_access_token()
    upload_url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
    if not os.path.exists(abs_path):
        raise WeChatError(f"文件不存在: {abs_path}")
    async with httpx.AsyncClient(timeout=30) as client:
        with open(abs_path, "rb") as f:
            files = {"media": (os.path.basename(abs_path), f, "image/jpeg")}
            resp = await client.post(upload_url, files=files)
            data = resp.json()
    if "media_id" not in data:
        raise WeChatError(f"上传图片失败: {data}")
    return data["media_id"], data.get("url", "")


def truncate_utf8(text: str, max_bytes: int) -> str:
    if text is None:
        return ""
    b = text.encode("utf-8")
    if len(b) <= max_bytes:
        return text
    return b[:max_bytes].decode("utf-8", errors="ignore")


def truncate_title(text: str) -> str:
    """
    微信标题严格限制，经验上控制在更紧的上限以避免 45003。
    规则：去空格 -> 最多 12 字符 -> 最多 30 字节。
    """
    if not text:
        return "未命名"
    text = text.strip()
    text = text[:12]
    text = truncate_utf8(text, 30)
    return text or "未命名"


def markdown_to_wechat_html(md: str, img_map: Dict[str, str]) -> str:
    """
    简单 Markdown -> HTML 转换，替换图片为微信返回的 URL。
    """
    import re

    def repl_img(match):
        url = match.group(1)
        mapped = img_map.get(url, url)
        return f'<img src="{mapped}" alt="image" />'

    # 替换图片
    md = re.sub(r"!\[[^\]]*\]\(([^)]+)\)", repl_img, md)
    # 去掉时间戳链接，保留文本
    md = re.sub(r"\[([0-9]{2}:[0-9]{2})\]\(timestamp\)", r"\1", md)

    # 转为段落
    paragraphs = [p.strip() for p in md.split("\n\n") if p.strip()]
    html_parts = [f"<p>{p.replace(chr(10), '<br/>')}</p>" for p in paragraphs]
    return "\n".join(html_parts)


async def create_draft(project_title: str, summary: str, markdown: str, image_paths: List[str]) -> str:
    """
    上传图片 -> 生成图文 -> 创建草稿，返回 draft media_id
    """
    token = await get_access_token()

    # 上传图片并映射
    img_map: Dict[str, str] = {}
    media_ids: List[str] = []
    for p in image_paths:
        try:
            media_id, url = await upload_image(p)
            media_ids.append(media_id)
            # 记录原始相对路径（/static/...）和本地路径的映射
            rel_key = p.replace("\\", "/")
            if rel_key.startswith("./"):
                rel_key = rel_key[2:]
            if not rel_key.startswith("/"):
                rel_key = "/" + rel_key
            img_map[rel_key] = url or ""
        except Exception as exc:
            # 忽略单张失败
            continue

    content_html = markdown_to_wechat_html(markdown, img_map)
    thumb_media_id = media_ids[0] if media_ids else None

    draft_url = f"https://api.weixin.qq.com/cgi-bin/draft/add?access_token={token}"
    # 微信标题限制严格，先用字符/字节双重截断
    title = truncate_title(project_title or "未命名")
    raw_digest = (summary or "").strip()
    # 再次收紧描述长度，控制在 60 字节以内，避免 45004
    digest = truncate_utf8(raw_digest, 60) or "摘要待补充"
    article = {
        "title": title,
        "author": "Sky",
        "digest": digest,
        "content": content_html,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    payload = {"articles": [article]}
    body = json.dumps(payload, ensure_ascii=False)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(draft_url, content=body.encode("utf-8"), headers={"Content-Type": "application/json; charset=utf-8"})
        data = resp.json()
    if "media_id" not in data:
        raise WeChatError(f"创建草稿失败: {data}")
    return data["media_id"]
