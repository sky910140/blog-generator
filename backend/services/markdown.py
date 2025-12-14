from typing import Dict, List


def format_timestamp(ts: int) -> str:
    minutes = ts // 60
    seconds = ts % 60
    return f"{minutes:02d}:{seconds:02d}"


def build_markdown(summary: str | None, steps: List[Dict]) -> str:
    parts = []
    if summary:
        parts.append(f"## 简介\n\n{summary}\n")
    parts.append("## 步骤\n")

    for step in steps:
        ts = step.get("timestamp", 0)
        title = step.get("title", "步骤")
        desc = step.get("description", "")
        image = step.get("image_path")
        ts_label = format_timestamp(ts)
        parts.append(f"### {title} [{ts_label}](timestamp)\n")
        if desc:
            parts.append(desc + "\n")
        if image:
            parts.append(f"![{title}]({image})\n")
        parts.append("")  # spacing

    return "\n".join(parts).strip() + "\n"
