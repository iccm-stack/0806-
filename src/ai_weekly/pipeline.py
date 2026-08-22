from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .analysis import build_report_data, prefilter_candidates, rank_candidates, select_events
from .collectors import collect_all, enrich_events
from .groq import GroqClient
from .mailer import send_email
from .render import render_email_html, render_markdown


LOGGER = logging.getLogger(__name__)


def run(root: Path, *, now: datetime | None = None, send_mail: bool = True) -> Path:
    now = (now or datetime.now(UTC)).astimezone(UTC)
    since = now - timedelta(days=7)
    state_path = root / "data" / "state.json"
    state = _load_state(state_path)

    candidates = collect_all(root / "config" / "sources.json", since)
    LOGGER.info("collected_candidates=%d", len(candidates))
    if not candidates:
        raise RuntimeError("No candidates collected; check source availability before publishing an empty report")

    client = GroqClient()
    candidates = prefilter_candidates(candidates)
    LOGGER.info("prefiltered_candidates=%d", len(candidates))
    ranked = rank_candidates(client, candidates)
    previous_keys = {
        key
        for weekly in state.get("weeks", [])
        for key in weekly.get("event_keys", [])
    }
    selected = select_events(ranked, previous_keys)
    if not selected:
        raise RuntimeError("No new high-value events were selected")
    selected = enrich_events(selected)

    period_start = since.date().isoformat()
    period_end = now.date().isoformat()
    report_data = build_report_data(client, selected, state.get("weeks", []), period_start, period_end)

    report_relative = Path("reports") / now.strftime("%Y") / f"{now.date().isoformat()}.md"
    report_path = root / report_relative
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_markdown(report_data), encoding="utf-8")

    report_url = _report_url(report_relative)
    mailed = False
    if send_mail:
        mailed = send_email(
            f"全球 AI 科技情報週報｜{now.date().isoformat()}",
            render_email_html(report_data, report_url),
        )
        if not mailed:
            LOGGER.warning("email_skipped reason=SMTP settings are incomplete")

    state.setdefault("weeks", []).append(
        {
            "period_end": period_end,
            "event_keys": [event.event_key for event in selected],
            "trend_names": [
                item.get("name", "") if isinstance(item, dict) else str(item)
                for item in report_data.get("weekly_trends", [])
            ],
            "one_line_summary": report_data.get("one_line_summary", ""),
            "report": report_relative.as_posix(),
            "email_sent": mailed,
        }
    )
    state["weeks"] = state["weeks"][-52:]
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report_path


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "weeks": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _report_url(relative_path: Path) -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com").rstrip("/")
    repository = os.environ.get("GITHUB_REPOSITORY", "iccm-stack/0806-")
    return f"{server}/{repository}/blob/main/{relative_path.as_posix()}"
