from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Repository:
    rank: int
    full_name: str
    url: str
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    stars_today: int = 0
    topics: List[str] = field(default_factory=list)
    license: str = ""
    created_at: str = ""
    updated_at: str = ""
    open_issues: int = 0
    default_branch: str = ""
    readme_excerpt: str = ""
    metadata_error: str = ""
    is_new: bool = False
    previous_rank: Optional[int] = None
    rank_change: Optional[int] = None
    streak_days: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Repository":
        fields = cls.__dataclass_fields__
        return cls(**{key: val for key, val in value.items() if key in fields})


@dataclass
class RepoInsight:
    full_name: str
    technology_summary: str
    application_domains: List[str]
    primary_use_cases: List[str]
    novelty_reason: str
    adoption_signal: str
    risks_or_limits: str

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "RepoInsight":
        return cls(
            full_name=str(value["full_name"]),
            technology_summary=str(value["technology_summary"]),
            application_domains=[str(v) for v in value["application_domains"]],
            primary_use_cases=[str(v) for v in value["primary_use_cases"]],
            novelty_reason=str(value["novelty_reason"]),
            adoption_signal=str(value["adoption_signal"]),
            risks_or_limits=str(value["risks_or_limits"]),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIAnalysis:
    daily_insights: List[str]
    repositories: List[RepoInsight]
    available: bool = True
    error: str = ""

    @classmethod
    def unavailable(cls, error: str) -> "AIAnalysis":
        return cls(daily_insights=[], repositories=[], available=False, error=error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "error": self.error,
            "daily_insights": self.daily_insights,
            "repositories": [repo.to_dict() for repo in self.repositories],
        }

