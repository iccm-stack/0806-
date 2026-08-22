from __future__ import annotations

import html
from typing import Any


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        f"# 全球 AI 科技情報週報｜{data.get('period_end', '')}",
        "",
        f"> **本週一句話：** {data.get('one_line_summary', '本週無足夠高價值情報。')}",
        "",
        f"涵蓋期間：{data.get('period_start', '')} ～ {data.get('period_end', '')}",
        "",
        "## Top 重大事件",
        "",
    ]
    analyses = data.get("events", [])
    selected = data.get("selected_events", [])
    if analyses:
        for index, event in enumerate(analyses, 1):
            lines.extend(_render_event(index, event))
    else:
        for index, event in enumerate(selected, 1):
            lines.extend(_render_fallback_event(index, event))

    lines.extend(_render_named_items("本週 AI 趨勢", data.get("weekly_trends", [])))
    lines.extend(_render_section("跨週變化", data.get("week_over_week_changes", [])))
    lines.extend(_render_section("6～24 個月展望（推測）", data.get("outlook_6_24_months", [])))
    lines.extend(_render_section("潛在機會", data.get("opportunities", [])))
    lines.extend(_render_section("潛在風險", data.get("risks", [])))
    lines.extend(_render_section("個人行動建議", data.get("personal_actions", [])))
    lines.extend(_render_section("值得試的工具", data.get("tools_to_try", [])))
    lines.extend(
        [
            "## 方法與聲明",
            "",
            str(data.get("methodology_note", "事實以原始來源為優先；分析與預測不代表確定結果。")),
            "",
            "本週報由自動化系統產生。請在做出重大決策前回查原始來源。",
            "",
        ]
    )
    return "\n".join(lines)


def render_email_html(data: dict[str, Any], report_url: str) -> str:
    summary = html.escape(str(data.get("one_line_summary", "")))
    events = data.get("events", []) or data.get("selected_events", [])
    items = []
    for event in events[:10]:
        title = html.escape(str(event.get("title", "")))
        url = html.escape(str(event.get("url", "")), quote=True)
        reason = html.escape(str(event.get("why_it_matters") or event.get("rationale") or ""))
        items.append(f'<li><p><a href="{url}"><strong>{title}</strong></a><br>{reason}</p></li>')
    trends = "".join(
        f"<li>{html.escape(str(item.get('name', item) if isinstance(item, dict) else item))}</li>"
        for item in data.get("weekly_trends", [])[:3]
    )
    return f"""<!doctype html><html lang="zh-Hant"><body style="font-family:Arial,sans-serif;line-height:1.65;max-width:760px;margin:auto;padding:24px">
<h1>全球 AI 科技情報週報</h1><blockquote>{summary}</blockquote>
<h2>本週 Top 事件</h2><ol>{''.join(items)}</ol>
<h2>本週趨勢</h2><ul>{trends}</ul>
<p><a href="{html.escape(report_url, quote=True)}">閱讀 GitHub 完整深度版</a></p>
<hr><small>自動產生的情報分析；預測不代表確定結果，重要決策請回查原始來源。</small>
</body></html>"""


def _render_event(index: int, event: dict[str, Any]) -> list[str]:
    title = event.get("title", f"事件 {index}")
    url = event.get("url", "")
    lines = [f"### {index}. [{title}]({url})", ""]
    lines.append(f"- **來源：** {event.get('source', '')}")
    lines.append(f"- **重要性評分：** {event.get('score', 'N/A')}")
    facts = event.get("confirmed_facts", [])
    if facts:
        lines.extend(["", "**已確認事實**", ""] + [f"- {item}" for item in facts])
    for label, key in [
        ("分析判斷", "analysis"),
        ("為什麼重要", "why_it_matters"),
        ("技術意義", "technical_significance"),
        ("產品／商業影響", "business_impact"),
        ("限制與未知", "limitations"),
    ]:
        if event.get(key):
            lines.extend(["", f"**{label}：** {event[key]}"])
    if event.get("deep_dive"):
        lines.extend(["", "#### 技術突破深度分析", ""])
        for key, value in event["deep_dive"].items():
            lines.append(f"- **{key.replace('_', ' ')}：** {_stringify(value)}")
    lines.append("")
    return lines


def _render_fallback_event(index: int, event: dict[str, Any]) -> list[str]:
    return [
        f"### {index}. [{event.get('title', '')}]({event.get('url', '')})",
        "",
        f"- **來源：** {event.get('source', '')}",
        f"- **摘要：** {event.get('summary', '')}",
        f"- **重要性：** {event.get('rationale', '')}",
        "",
    ]


def _render_named_items(title: str, items: list[Any]) -> list[str]:
    lines = [f"## {title}", ""]
    for item in items:
        if isinstance(item, dict):
            lines.append(f"### {item.get('name', '趨勢')}")
            lines.append("")
            for key in ("evidence", "assessment"):
                if item.get(key):
                    lines.append(f"- **{key}：** {_stringify(item[key])}")
        else:
            lines.append(f"- {item}")
    lines.append("")
    return lines


def _render_section(title: str, value: Any) -> list[str]:
    lines = [f"## {title}", ""]
    if isinstance(value, list):
        lines.extend(f"- {_stringify(item)}" for item in value)
    elif value:
        lines.append(_stringify(value))
    else:
        lines.append("本週沒有足夠證據形成可靠判斷。")
    lines.append("")
    return lines


def _stringify(value: Any) -> str:
    if isinstance(value, dict):
        return "；".join(f"{key}: {_stringify(item)}" for key, item in value.items())
    if isinstance(value, list):
        return "；".join(_stringify(item) for item in value)
    return str(value)

