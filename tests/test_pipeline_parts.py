import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from ai_weekly.analysis import select_events
from ai_weekly.collectors import collect_html_page, deduplicate_candidates
from ai_weekly.models import Candidate, RankedEvent
from ai_weekly.render import render_markdown


def _candidate(title: str, url: str) -> Candidate:
    return Candidate(title=title, url=url, source="Official", published_at="2026-08-20T00:00:00+00:00")


def _event(key: str, score: float) -> RankedEvent:
    return RankedEvent(
        event_key=key,
        title=key,
        url=f"https://example.com/{key}",
        source="Official",
        published_at="2026-08-20T00:00:00+00:00",
        category="model",
        summary="summary",
        total_score=score,
    )


class PipelinePartsTests(unittest.TestCase):
    def test_deduplicates_canonical_url_and_title(self):
        items = [
            _candidate("New Model", "https://example.com/model"),
            _candidate("New Model", "https://another.example/model"),
            _candidate("Different", "https://example.com/model#details"),
        ]
        self.assertEqual(len(deduplicate_candidates(items)), 1)

    def test_selection_excludes_previously_covered_event(self):
        events = [_event("old", 9.5), _event("new", 8.0), _event("minor", 3.0)]
        selected = select_events(events, {"old"})
        self.assertEqual([item.event_key for item in selected], ["new", "minor"])

    def test_render_labels_fact_analysis_and_forecast(self):
        markdown = render_markdown(
            {
                "period_end": "2026-08-22",
                "events": [
                    {
                        "title": "Model X",
                        "url": "https://example.com/x",
                        "confirmed_facts": ["官方已發布"],
                        "analysis": "可能影響開發流程",
                    }
                ],
                "outlook_6_24_months": ["若採用率持續，生態系可能擴大"],
            }
        )
        self.assertIn("已確認事實", markdown)
        self.assertIn("分析判斷", markdown)
        self.assertIn("6～24 個月展望（推測）", markdown)

    @patch("ai_weekly.collectors._get")
    def test_anthropic_newsroom_fallback(self, mocked_get):
        mocked_get.return_value = b'''<div class="PublicationList">
        <a href="/news/model-x"><time>Aug 21, 2026</time>
        <span class="PublicationList__title">Introducing Model X</span></a></div>'''
        items = collect_html_page(
            {"name": "Anthropic", "url": "https://www.anthropic.com/news", "layout": "anthropic_news"},
            datetime(2026, 8, 15, tzinfo=UTC),
        )
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].url, "https://www.anthropic.com/news/model-x")


if __name__ == "__main__":
    unittest.main()
