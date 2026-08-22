from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class Candidate:
    title: str
    url: str
    source: str
    published_at: str
    summary: str = ""
    tier: int = 2
    source_kind: str = "official"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RankedEvent:
    event_key: str
    title: str
    url: str
    source: str
    published_at: str
    category: str
    summary: str
    scores: dict[str, int] = field(default_factory=dict)
    total_score: float = 0.0
    rationale: str = ""
    is_major_breakthrough: bool = False
    related_urls: list[str] = field(default_factory=list)
    evidence_excerpt: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RankedEvent":
        allowed = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in allowed})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
