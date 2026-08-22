from __future__ import annotations

import hashlib
import json
from collections import Counter
from typing import Any

from .groq import GroqClient
from .models import Candidate, RankedEvent


RANK_SYSTEM = """你是全球 AI 科技情報分析師。只依據輸入資料判斷，不得虛構事實。
可信度優先順序：官方/原始研究 > 高品質媒體 > 專業社群。
技術突破永遠優先於一般職涯資訊；Agent、AI Coding、資料工程、企業 AI、雲端 AI 只作加權。
輸出必須是合法 JSON object，且所有文字用繁體中文。"""

REPORT_SYSTEM = """你是嚴謹的全球 AI 科技情報主編。只可使用提供的候選資料與歷史摘要，
清楚區分已確認事實、分析判斷與未來推測，不把預測寫成必然。合併同一事件，保留原始來源連結。
技術突破優先，其次是重大產品/商業/產業，再來才是工具。輸出必須是合法 JSON object，使用繁體中文。"""


IMPORTANT_KEYWORDS = (
    "model", "reason", "agent", "coding", "multimodal", "training", "inference",
    "benchmark", "research", "paper", "open source", "enterprise", "cloud", "chip",
    "模型", "推理", "代理", "多模態", "訓練", "論文", "開源", "雲端", "晶片",
)


def prefilter_candidates(candidates: list[Candidate], maximum: int = 45, per_source: int = 6) -> list[Candidate]:
    """Cheap, deterministic prefilter before spending scarce LLM tokens."""
    def priority(item: Candidate) -> tuple[int, str]:
        text = f"{item.title} {item.summary}".lower()
        keyword_hits = sum(1 for keyword in IMPORTANT_KEYWORDS if keyword in text)
        source_bonus = 3 if item.source_kind == "original_research" else 2 if item.source_kind == "official" else 0
        return (10 - item.tier * 3 + source_bonus + min(keyword_hits, 5), item.published_at)

    counts: Counter[str] = Counter()
    selected: list[Candidate] = []
    for item in sorted(candidates, key=priority, reverse=True):
        if counts[item.source] >= per_source:
            continue
        selected.append(item)
        counts[item.source] += 1
        if len(selected) >= maximum:
            break
    return selected


def rank_candidates(client: GroqClient, candidates: list[Candidate], batch_size: int = 10) -> list[RankedEvent]:
    ranked: list[RankedEvent] = []
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start : start + batch_size]
        payload = []
        for idx, item in enumerate(batch):
            compact = item.to_dict()
            compact["summary"] = compact["summary"][:500]
            payload.append(dict(index=start + idx, **compact))
        prompt = f"""評估以下候選情報。對每項給 0～10 整數分數：
technical_breakthrough, research_novelty, product_impact, practical_value,
industry_impact, open_source_impact, future_potential, career_relevance, source_confidence。
計算 total_score（技術與研究權重最高，職涯最低），判斷 category 與 is_major_breakthrough。
event_key 請用能跨週穩定識別同一事件的簡短英文 slug；若無法產生可留空。
輸出格式：{{"events":[{{"index":0,"event_key":"...","category":"...","summary":"...",
"scores":{{...}},"total_score":0,"rationale":"...","is_major_breakthrough":false}}]}}。

候選資料：
{json.dumps(payload, ensure_ascii=False)}"""
        response = client.complete_json(system=RANK_SYSTEM, user=prompt, max_tokens=2500)
        for item in response.get("events", []):
            try:
                index = int(item["index"])
                candidate = candidates[index]
            except (KeyError, TypeError, ValueError, IndexError):
                continue
            scores = {key: _bounded_int(value) for key, value in item.get("scores", {}).items()}
            event_key = str(item.get("event_key") or _fallback_event_key(candidate))[:100]
            ranked.append(
                RankedEvent(
                    event_key=event_key,
                    title=candidate.title,
                    url=candidate.url,
                    source=candidate.source,
                    published_at=candidate.published_at,
                    category=str(item.get("category", "其他"))[:80],
                    summary=str(item.get("summary", candidate.summary))[:1200],
                    scores=scores,
                    total_score=float(item.get("total_score", _weighted_score(scores))),
                    rationale=str(item.get("rationale", ""))[:1000],
                    is_major_breakthrough=bool(item.get("is_major_breakthrough", False)),
                )
            )
    return sorted(ranked, key=lambda event: event.total_score, reverse=True)


def select_events(ranked: list[RankedEvent], previous_keys: set[str], minimum: int = 5, maximum: int = 8) -> list[RankedEvent]:
    fresh = [event for event in ranked if event.event_key not in previous_keys]
    thresholded = [event for event in fresh if event.total_score >= 6.0]
    count = min(maximum, max(minimum, len(thresholded)))
    return fresh[:count]


def build_report_data(
    client: GroqClient,
    events: list[RankedEvent],
    history: list[dict[str, Any]],
    period_start: str,
    period_end: str,
) -> dict[str, Any]:
    prompt = f"""請將本週 Top 事件製作成深度週報資料。
每個事件至少包含：title, source, url, confirmed_facts（陣列）, analysis, why_it_matters,
technical_significance, business_impact, score, limitations。
若 major_breakthrough=true，再加入 deep_dive，包含 principles, method_or_architecture,
benchmarks, comparison, limitations, differing_views, next_signals。
另產生：one_line_summary、weekly_trends（1～3 項，每項含 name/evidence/assessment）、
week_over_week_changes、outlook_6_24_months（須標示為推測）、opportunities、risks、
personal_actions、tools_to_try、methodology_note。

期間：{period_start} 至 {period_end}
本週事件：{json.dumps([event.to_dict() for event in events], ensure_ascii=False)}
過去最多四週摘要：{json.dumps(history[-4:], ensure_ascii=False)}
輸出格式為上述欄位組成的 JSON object。"""
    response = client.complete_json(system=REPORT_SYSTEM, user=prompt, max_tokens=4200)
    response["period_start"] = period_start
    response["period_end"] = period_end
    response["selected_events"] = [event.to_dict() for event in events]
    return response


def _fallback_event_key(candidate: Candidate) -> str:
    digest = hashlib.sha256(candidate.url.split("?", 1)[0].encode("utf-8")).hexdigest()[:16]
    return f"event-{digest}"


def _bounded_int(value: Any) -> int:
    try:
        return max(0, min(10, int(value)))
    except (TypeError, ValueError):
        return 0


def _weighted_score(scores: dict[str, int]) -> float:
    weights = {
        "technical_breakthrough": 1.5,
        "research_novelty": 1.3,
        "product_impact": 1.0,
        "practical_value": 0.9,
        "industry_impact": 1.0,
        "open_source_impact": 0.7,
        "future_potential": 1.1,
        "career_relevance": 0.4,
        "source_confidence": 0.8,
    }
    denominator = sum(weights.values())
    return round(sum(scores.get(key, 0) * weight for key, weight in weights.items()) / denominator, 2)
