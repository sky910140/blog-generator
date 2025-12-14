import logging
import math
import mimetypes
import time
from typing import Any, Dict, List

import google.generativeai as gen
from google.api_core import exceptions as google_exceptions
import json


PROMPT = """你是“人生进化指南”主理人 Sky 的口吻，和读者并肩同行，不说教。请观看视频，用通俗、温暖、接地气的语言写给初学者，必要时举例或比喻，让零基础也能跟做。输出结构化 JSON（不要返回多余文本）。
输出格式:
{
  "headline": "吸引人、有深度、不浮夸的标题，避免“课程/教程/入门课”等字样，可用“技巧/诀窍/心法” framing",
  "summary": "一句话摘要",
  "steps": [
    {
      "step_index": 1,
      "timestamp": 125,  # 使用秒，取整
      "title": "步骤标题（简短）",
      "description": "详细操作说明，语气友好，结合“为什么这么做”+“怎么做”，给出注意点/踩坑提醒/小贴士，必要时举例或比喻"
    }
  ]
}
要求：
- 选择 4-10 个关键步骤，覆盖完整流程，时间戳使用秒且递增。
- 语言友好、口语化，避免生硬术语；有术语用括号解释；给出“为什么”和“怎么做”。
- 像同行者分享经验，可穿插“我”的体会/踩坑/提醒，让读者安心；适当比喻（风暴与星光、泥泞与道路等）。
- 如无明确步骤，提炼主要画面变化/操作节点，并说明意义。
- 若有代码或配置，描述核心片段的作用与效果，不粘贴长代码。
- 只返回 JSON。
"""


class AIEngine:
    """
    Gemini 1.5 调用封装；若未配置 API Key，则回退到占位生成。
    """

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 120, model_name: str = "models/gemini-2.5-flash"):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.model_name = model_name

    def _synthetic_steps(self, duration: int) -> Dict[str, Any]:
        logging.warning("AIEngine: using synthetic steps (no API key or fallback).")
        steps = []
        step_count = max(4, min(8, math.ceil(duration / 120)))
        interval = max(10, duration // (step_count + 1))
        for idx in range(step_count):
            timestamp = min(duration - 1, (idx + 1) * interval)
            steps.append(
                {
                    "step_index": idx + 1,
                    "timestamp": timestamp,
                    "title": f"步骤 {idx + 1}",
                    "description": f"在 {timestamp} 秒附近的关键操作描述。",
                }
            )
        return {"summary": "自动生成的占位摘要。请替换为真实 AI 输出。", "steps": steps}

    def _upload_video(self, video_path: str):
        mime, _ = mimetypes.guess_type(video_path)
        file = gen.upload_file(path=video_path, mime_type=mime or "video/mp4")
        start = time.time()
        while file.state.name == "PROCESSING":
            if time.time() - start > self.timeout_seconds:
                raise TimeoutError("Gemini 视频上传超时")
            time.sleep(2)
            file = gen.get_file(file.name)
        if file.state.name != "ACTIVE":
            raise RuntimeError(f"Gemini 文件状态异常: {file.state.name}")
        return file

    def _parse_response(self, resp) -> Dict[str, Any]:
        """
        Parse Gemini response text to JSON. Assumes model returns JSON string per prompt.
        """
        text = ""
        if hasattr(resp, "text"):
            text = resp.text
        elif hasattr(resp, "candidates") and resp.candidates:
            parts = resp.candidates[0].content.parts
            text = "".join(getattr(p, "text", "") for p in parts)
        try:
            return json.loads(text)
        except Exception:
            raise ValueError("无法解析 Gemini 返回结果为 JSON")

    def generate_steps(self, video_path: str, duration: int) -> Dict[str, Any]:
        if not self.api_key:
            # 无 Key 时退回占位逻辑
            return self._synthetic_steps(duration)

        gen.configure(api_key=self.api_key)
        model_candidates = [
            self.model_name,
            "models/gemini-2.5-flash",
            "models/gemini-2.0-flash",
            "models/gemini-flash-latest",
            "models/gemini-pro-latest",
        ]

        last_error: Exception | None = None
        for model_name in model_candidates:
            try:
                logging.info("AIEngine: using model %s", model_name)
                model = gen.GenerativeModel(
                    model_name,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": 0.2,
                    },
                )
                file = self._upload_video(video_path)
                resp = model.generate_content(
                    [PROMPT, file],
                    request_options={"timeout": self.timeout_seconds},
                )
                return self._parse_response(resp)
            except google_exceptions.NotFound as exc:
                last_error = exc
                logging.warning("AIEngine: model %s not found, trying next. error=%s", model_name, exc)
                continue
            except Exception as exc:  # broad catch to fallback gracefully
                last_error = exc
                logging.exception("AIEngine: Gemini call failed with model %s", model_name)
                break

        # 回退到占位生成，避免整个流程失败
        return self._synthetic_steps(duration)


def build_ai_engine(api_key: str | None, timeout_seconds: int, model_name: str) -> AIEngine:
    return AIEngine(api_key=api_key, timeout_seconds=timeout_seconds, model_name=model_name)
