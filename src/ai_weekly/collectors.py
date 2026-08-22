from __future__ import annotations

import email.utils
import html
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .groq import USER_AGENT
from .models import Candidate, RankedEvent


LOGGER = logging.getLogger(__name__)
TAG_RE = re.compile(r"<[^>]+>")


def collect_all(config_path: Path, since: datetime) -> list[Candidate]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    candidates: list[Candidate] = []
    for source in config.get("feeds", []):
        try:
            candidates.extend(collect_feed(source, since))
        except Exception as exc:  # One broken publisher must not stop the weekly.
            LOGGER.warning("source_failed name=%s error=%s", source.get("name"), exc)
    for source in config.get("arxiv", []):
        try:
            candidates.extend(collect_arxiv(source, since))
        except Exception as exc:
            LOGGER.warning("source_failed name=%s error=%s", source.get("name"), exc)
    for source in config.get("html_pages", []):
        try:
            candidates.extend(collect_html_page(source, since))
        except Exception as exc:
            LOGGER.warning("source_failed name=%s error=%s", source.get("name"), exc)
    return deduplicate_candidates(candidates)


def collect_feed(source: dict, since: datetime) -> list[Candidate]:
    root = ET.fromstring(_get(source["url"]))
    results: list[Candidate] = []
    entries = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for entry in entries:
        title = _text(entry, ["title", "{http://www.w3.org/2005/Atom}title"])
        url = _entry_url(entry)
        published = _text(
            entry,
            [
                "pubDate",
                "published",
                "updated",
                "{http://www.w3.org/2005/Atom}published",
                "{http://www.w3.org/2005/Atom}updated",
            ],
        )
        parsed_date = _parse_date(published)
        if not title or not url or (parsed_date and parsed_date < since):
            continue
        summary = _text(
            entry,
            [
                "description",
                "summary",
                "{http://www.w3.org/2005/Atom}summary",
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            ],
        )
        results.append(
            Candidate(
                title=_clean(title, 300),
                url=url.strip(),
                source=source["name"],
                published_at=(parsed_date or since).isoformat(),
                summary=_clean(summary, 1600),
                tier=int(source.get("tier", 2)),
                source_kind=source.get("kind", "official"),
            )
        )
    return results


def collect_arxiv(source: dict, since: datetime) -> list[Candidate]:
    query = source.get("query", "cat:cs.AI OR cat:cs.CL OR cat:cs.LG")
    params = urllib.parse.urlencode(
        {
            "search_query": query,
            "start": 0,
            "max_results": int(source.get("max_results", 40)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
    )
    root = ET.fromstring(_get(f"https://export.arxiv.org/api/query?{params}"))
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    results: list[Candidate] = []
    for entry in root.findall("atom:entry", ns):
        published = _parse_date(_text(entry, ["{http://www.w3.org/2005/Atom}published"]))
        if published and published < since:
            continue
        results.append(
            Candidate(
                title=_clean(_text(entry, ["{http://www.w3.org/2005/Atom}title"]), 300),
                url=_text(entry, ["{http://www.w3.org/2005/Atom}id"]),
                source=source.get("name", "arXiv"),
                published_at=(published or since).isoformat(),
                summary=_clean(_text(entry, ["{http://www.w3.org/2005/Atom}summary"]), 2000),
                tier=int(source.get("tier", 1)),
                source_kind="original_research",
            )
        )
    return results


def collect_html_page(source: dict, since: datetime) -> list[Candidate]:
    """Collect a publisher page when it does not provide a usable RSS feed.

    Layout parsers are explicit rather than pretending arbitrary HTML is a
    reliable feed. A site redesign therefore fails visibly and remains isolated.
    """
    document = _get(source["url"]).decode("utf-8", "ignore")
    if source.get("layout") != "anthropic_news":
        raise ValueError(f"Unsupported HTML layout: {source.get('layout')}")
    pattern = re.compile(
        r'<a\s+href="(?P<href>/news/[^"?#]+)"[^>]*>'
        r'.*?<time[^>]*>(?P<date>[^<]+)</time>'
        r'.*?<span[^>]*title[^>]*>(?P<title>[^<]+)</span>.*?</a>',
        re.IGNORECASE | re.DOTALL,
    )
    results: list[Candidate] = []
    for match in pattern.finditer(document):
        published = _parse_date(match.group("date"))
        if published and published < since:
            continue
        results.append(
            Candidate(
                title=_clean(match.group("title"), 300),
                url=urllib.parse.urljoin(source["url"], match.group("href")),
                source=source["name"],
                published_at=(published or since).isoformat(),
                tier=int(source.get("tier", 1)),
                source_kind=source.get("kind", "official"),
            )
        )
    if not results and "PublicationList" not in document:
        raise ValueError("Expected Anthropic newsroom structure was not found")
    return results


def deduplicate_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen_urls: set[str] = set()
    seen_titles: set[str] = set()
    result: list[Candidate] = []
    for item in sorted(candidates, key=lambda value: (value.tier, value.published_at)):
        normalized_url = item.url.split("#", 1)[0].rstrip("/")
        normalized_title = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", item.title.lower())
        if normalized_url in seen_urls or (normalized_title and normalized_title in seen_titles):
            continue
        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        result.append(item)
    return result


def enrich_events(events: list[RankedEvent]) -> list[RankedEvent]:
    """Attach a bounded excerpt from each original page for grounded analysis."""
    for event in events:
        try:
            document = _get(event.url).decode("utf-8", "ignore")
            article = re.search(r"<article\b[^>]*>(.*?)</article>", document, re.IGNORECASE | re.DOTALL)
            content = article.group(1) if article else document
            content = re.sub(r"<(script|style|svg|nav|footer)\b.*?</\1>", " ", content, flags=re.IGNORECASE | re.DOTALL)
            event.evidence_excerpt = _clean(content, 1200)
        except Exception as exc:
            LOGGER.warning("enrichment_failed url=%s error=%s", event.url, exc)
    return events


def _get(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html, application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return response.read(5_000_000)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in {429, 500, 502, 503, 504} or attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"Unable to fetch {url}: {last_error}")


def _text(element: ET.Element, names: list[str]) -> str:
    for name in names:
        child = element.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _entry_url(entry: ET.Element) -> str:
    direct = _text(entry, ["link", "guid"])
    if direct.startswith("http"):
        return direct
    for link in entry.findall("{http://www.w3.org/2005/Atom}link"):
        href = link.attrib.get("href", "")
        if href and link.attrib.get("rel", "alternate") == "alternate":
            return href
    return direct


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _clean(value: str, limit: int) -> str:
    value = html.unescape(TAG_RE.sub(" ", value or ""))
    return re.sub(r"\s+", " ", value).strip()[:limit]
