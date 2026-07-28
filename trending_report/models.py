from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

ANALYSIS_VERSION = 3


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
class Evidence:
    title: str
    url: str
    source_type: str

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "Evidence":
        return cls(
            title=str(value.get("title", "")),
            url=str(value.get("url", "")),
            source_type=str(value.get("source_type", "official")),
        )


@dataclass
class RepoInsight:
    full_name: str
    one_line_summary: str
    industry_direction: str
    target_users: List[str]
    problem_solved: str
    solution: str
    why_now: str
    noteworthy_technology: str
    technology_impact: str
    product_form: str
    commercialization_signal: str
    maturity: str
    risks: str
    ai_relevance: str
    plain_language_explanation: str
    scenario_examples: List[str]
    practical_benefits: List[str]
    industry_implications: str
    who_should_care: str
    validation_signals: List[str]
    confidence: str
    priority_score: int
    evidence: List[Evidence] = field(default_factory=list)
    deep_researched: bool = False

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "RepoInsight":
        return cls(
            full_name=str(value["full_name"]),
            one_line_summary=str(value["one_line_summary"]),
            industry_direction=str(value["industry_direction"]),
            target_users=[str(v) for v in value["target_users"]],
            problem_solved=str(value["problem_solved"]),
            solution=str(value["solution"]),
            why_now=str(value["why_now"]),
            noteworthy_technology=str(value["noteworthy_technology"]),
            technology_impact=str(value["technology_impact"]),
            product_form=str(value["product_form"]),
            commercialization_signal=str(value["commercialization_signal"]),
            maturity=str(value["maturity"]),
            risks=str(value["risks"]),
            ai_relevance=str(value["ai_relevance"]),
            plain_language_explanation=str(
                value.get("plain_language_explanation", value["one_line_summary"])
            ),
            scenario_examples=[
                str(v) for v in value.get("scenario_examples", [])
            ],
            practical_benefits=[
                str(v) for v in value.get("practical_benefits", [])
            ],
            industry_implications=str(
                value.get("industry_implications", value["ai_relevance"])
            ),
            who_should_care=str(value.get("who_should_care", "相关行业从业者")),
            validation_signals=[
                str(v) for v in value.get("validation_signals", [])
            ],
            confidence=str(value["confidence"]),
            priority_score=max(0, min(100, int(value["priority_score"]))),
            evidence=[
                Evidence.from_dict(item) for item in value.get("evidence", [])
            ],
            deep_researched=bool(value.get("deep_researched", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class IndustryAnalysis:
    key_judgments: List[str]
    hot_characteristics: List[str]
    product_business_signals: List[str]
    watch_next: List[str]
    repositories: List[RepoInsight]
    available: bool = True
    error: str = ""
    analysis_version: int = ANALYSIS_VERSION

    @classmethod
    def unavailable(
        cls,
        repositories: List[Repository],
        error: str,
    ) -> "IndustryAnalysis":
        placeholders = [
            RepoInsight(
                full_name=repo.full_name,
                one_line_summary=repo.description or "行业分析待生成",
                industry_direction="行业分析待生成",
                target_users=["待分析"],
                problem_solved=repo.description or "待分析",
                solution="待分析",
                why_now="仅确认该项目进入 GitHub Trending，尚未完成行业判断。",
                noteworthy_technology="待分析",
                technology_impact="待分析",
                product_form="待分析",
                commercialization_signal="待分析",
                maturity="待分析",
                risks="缺少 AI 行业分析，不能据此判断市场采用或商业价值。",
                ai_relevance="待分析",
                plain_language_explanation="待分析",
                scenario_examples=["待分析"],
                practical_benefits=["待分析"],
                industry_implications="待分析",
                who_should_care="待分析",
                validation_signals=["待分析"],
                confidence="低",
                priority_score=0,
            )
            for repo in repositories
        ]
        return cls(
            key_judgments=[],
            hot_characteristics=[],
            product_business_signals=[],
            watch_next=[],
            repositories=placeholders,
            available=False,
            error=error,
        )

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "IndustryAnalysis":
        return cls(
            key_judgments=[str(v) for v in value.get("key_judgments", [])],
            hot_characteristics=[
                str(v) for v in value.get("hot_characteristics", [])
            ],
            product_business_signals=[
                str(v) for v in value.get("product_business_signals", [])
            ],
            watch_next=[str(v) for v in value.get("watch_next", [])],
            repositories=[
                RepoInsight.from_dict(item)
                for item in value.get("repositories", [])
            ],
            available=bool(value.get("available", True)),
            error=str(value.get("error", "")),
            analysis_version=int(value.get("analysis_version", ANALYSIS_VERSION)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_version": self.analysis_version,
            "available": self.available,
            "error": self.error,
            "key_judgments": self.key_judgments,
            "hot_characteristics": self.hot_characteristics,
            "product_business_signals": self.product_business_signals,
            "watch_next": self.watch_next,
            "repositories": [repo.to_dict() for repo in self.repositories],
        }
