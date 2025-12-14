import logging
import math
import mimetypes
import time
import json
from typing import Any, Dict

import google.generativeai as gen
from google.api_core import exceptions as google_exceptions


PROMPT = """你是“人类进化指南”导师 Sky，用口语化、共情的语气给初学者讲解视频内容。请观看视频，只输出 JSON（不要额外文字）。
输出格式:
{
  "headline": "有吸引力的标题，避免“教程/课程/讲解”等，可用“技巧/方法/避坑”等 framing",
  "summary": "一两句话摘要",
  "steps": [
    {
      "step_index": 1,
      "timestamp": 125,  // 单位秒，取整
      "title": "步骤标题（简洁）",
      "description": "详细操作说明，口语化，包含为什么/怎么做/注意事项/提醒/常见坑，可给例子"
    }
  ]
}
要求:
- 选 4-10 个关键步骤，覆盖完整流程，时间戳用秒并递增
- 语言亲和、准确；给出“为什么/怎么做”，适当提醒/避坑/例子
- 如有代码/配置，描述关键片段和效果，不要长代码块
- 如果无法识别视频内容，返回 {"reason": "...无法识别原因...", "steps": []}
- 只返回 JSON
"""


class AIEngine:
    """
    Gemini 调用封装；若无 API Key 则返回占位结果。
    """

    def __init__(self, api_key: str | None = None, timeout_seconds: int = 120, model_name: str = "models/gemini-2.5-flash"):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.model_name = model_name

    def _synthetic_steps(self, duration: int) -> Dict[str, Any]:
        logging.warning("AIEngine: using synthetic steps (no API key or fallback).")
        steps = []
        step_count = max(4, min(8, math.ceil(duration / 120))) if duration > 0 else 4
        interval = max(10, duration // (step_count + 1)) if duration > 0 else 10
        for idx in range(step_count):
            timestamp = min(max(duration - 1, 0), (idx + 1) * interval)
            steps.append(
                {
                    "step_index": idx + 1,
                    "timestamp": timestamp,
                    "title": f"步骤 {idx + 1}",
                    "description": f"在 {timestamp} 秒的关键操作描述（占位，未调用真实 AI）。",
                }
            )
        return {
            "headline": "占位标题（未调用真实 AI）",
            "summary": "自动生成的占位摘要（未调用真实 AI，请配置 GEMINI_API_KEY）。",
            "steps": steps,
        }

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

        # 退回占位生成，避免流程失败
        return self._synthetic_steps(duration)


def build_ai_engine(api_key: str | None, timeout_seconds: int, model_name: str) -> AIEngine:
    return AIEngine(api_key=api_key, timeout_seconds=timeout_seconds, model_name=model_name)
