from __future__ import annotations

import json
import re
import time
from base64 import b64decode
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import Evidence, IndustryAnalysis, RepoInsight, Repository
from .parser import parse_trending_html

USER_AGENT = "github-trending-insights/0.2"


class HTTPClient:
    def __init__(self, retries: int = 3, timeout: int = 20) -> None:
        self.retries = retries
        self.timeout = timeout

    def request(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[bytes] = None,
        method: Optional[str] = None,
    ) -> bytes:
        request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
        last_error: Optional[Exception] = None
        for attempt in range(self.retries):
            try:
                request = Request(url, headers=request_headers, data=data, method=method)
                with urlopen(request, timeout=self.timeout) as response:
                    return response.read()
            except HTTPError as exc:
                last_error = exc
                if exc.code not in {429, 500, 502, 503, 504}:
                    break
            except (URLError, TimeoutError) as exc:
                last_error = exc
            if attempt + 1 < self.retries:
                time.sleep(2**attempt)
        raise RuntimeError(f"请求失败：{url}（{type(last_error).__name__}）") from last_error


class GitHubClient:
    def __init__(self, token: str = "", http: Optional[HTTPClient] = None) -> None:
        self.token = token
        self.http = http or HTTPClient()

    @property
    def headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def fetch_trending(self, limit: int = 25) -> List[Repository]:
        body = self.http.request(
            "https://github.com/trending?since=daily",
            headers={"Accept": "text/html"},
        )
        return parse_trending_html(body.decode("utf-8", errors="replace"), limit=limit)

    def enrich(self, repository: Repository) -> Repository:
        slug = quote(repository.full_name, safe="/")
        try:
            metadata = self._json(f"https://api.github.com/repos/{slug}")
            repository.description = metadata.get("description") or repository.description
            repository.language = metadata.get("language") or repository.language
            repository.stars = int(metadata.get("stargazers_count") or repository.stars)
            repository.forks = int(metadata.get("forks_count") or repository.forks)
            repository.topics = [str(topic) for topic in metadata.get("topics", [])]
            license_data = metadata.get("license") or {}
            repository.license = (
                license_data.get("spdx_id") or license_data.get("name") or ""
            )
            repository.created_at = metadata.get("created_at") or ""
            repository.updated_at = metadata.get("updated_at") or ""
            repository.open_issues = int(metadata.get("open_issues_count") or 0)
            repository.default_branch = metadata.get("default_branch") or ""
            repository.readme_excerpt = self._fetch_readme(slug)
        except Exception as exc:
            repository.metadata_error = f"{type(exc).__name__}: metadata unavailable"
        return repository

    def _json(self, url: str) -> Dict[str, Any]:
        body = self.http.request(url, headers=self.headers)
        return json.loads(body.decode("utf-8"))

    def _fetch_readme(self, slug: str, max_chars: int = 4_000) -> str:
        try:
            payload = self._json(f"https://api.github.com/repos/{slug}/readme")
            encoded = payload.get("content", "")
            if not encoded:
                return ""
            content = b64decode(encoded).decode("utf-8", errors="replace")
            return " ".join(content.split())[:max_chars]
        except Exception:
            return ""


PROJECT_PROPERTIES: Dict[str, Any] = {
    "full_name": {"type": "string"},
    "one_line_summary": {"type": "string"},
    "industry_direction": {"type": "string"},
    "target_users": {"type": "array", "items": {"type": "string"}},
    "problem_solved": {"type": "string"},
    "solution": {"type": "string"},
    "why_now": {"type": "string"},
    "noteworthy_technology": {"type": "string"},
    "technology_impact": {"type": "string"},
    "product_form": {"type": "string"},
    "commercialization_signal": {"type": "string"},
    "maturity": {"type": "string"},
    "risks": {"type": "string"},
    "ai_relevance": {"type": "string"},
    "confidence": {"type": "string", "enum": ["高", "中", "低"]},
    "priority_score": {"type": "integer", "minimum": 0, "maximum": 100},
}

CLASSIFICATION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "key_judgments",
        "hot_characteristics",
        "product_business_signals",
        "watch_next",
        "repositories",
    ],
    "properties": {
        "key_judgments": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "items": {"type": "string"},
        },
        "hot_characteristics": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {"type": "string"},
        },
        "product_business_signals": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {"type": "string"},
        },
        "watch_next": {
            "type": "array",
            "minItems": 2,
            "maxItems": 6,
            "items": {"type": "string"},
        },
        "repositories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(PROJECT_PROPERTIES),
                "properties": PROJECT_PROPERTIES,
            },
        },
    },
}

RESEARCH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["repositories"],
    "properties": {
        "repositories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "full_name",
                    "one_line_summary",
                    "why_now",
                    "noteworthy_technology",
                    "technology_impact",
                    "commercialization_signal",
                    "maturity",
                    "risks",
                    "confidence",
                    "evidence",
                ],
                "properties": {
                    "full_name": {"type": "string"},
                    "one_line_summary": {"type": "string"},
                    "why_now": {"type": "string"},
                    "noteworthy_technology": {"type": "string"},
                    "technology_impact": {"type": "string"},
                    "commercialization_signal": {"type": "string"},
                    "maturity": {"type": "string"},
                    "risks": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["高", "中", "低"]},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["title", "url", "source_type"],
                            "properties": {
                                "title": {"type": "string"},
                                "url": {"type": "string"},
                                "source_type": {
                                    "type": "string",
                                    "enum": ["project", "official", "academic"],
                                },
                            },
                        },
                    },
                },
            },
        }
    },
}

PERIODIC_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "executive_summary",
        "direction_changes",
        "customer_changes",
        "product_opportunities",
        "competition_changes",
        "commercial_signals",
        "risks",
        "watch_next",
    ],
    "properties": {
        "executive_summary": {"type": "array", "items": {"type": "string"}},
        "direction_changes": {"type": "array", "items": {"type": "string"}},
        "customer_changes": {"type": "array", "items": {"type": "string"}},
        "product_opportunities": {"type": "array", "items": {"type": "string"}},
        "competition_changes": {"type": "array", "items": {"type": "string"}},
        "commercial_signals": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "watch_next": {"type": "array", "items": {"type": "string"}},
    },
}


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-terra",
        research_model: str = "gpt-5.6-sol",
        http: Optional[HTTPClient] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.research_model = research_model
        self.http = http or HTTPClient(retries=2, timeout=120)

    def analyze(
        self,
        repositories: List[Repository],
        *,
        research_limit: int = 8,
    ) -> IndustryAnalysis:
        if not self.api_key:
            return IndustryAnalysis.unavailable(
                repositories,
                "未配置 OPENAI_API_KEY，行业分析待生成",
            )
        error = ""
        for _ in range(2):
            try:
                analysis = self._classify(repositories)
                break
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        else:
            return IndustryAnalysis.unavailable(
                repositories,
                f"行业分类重试后仍失败：{error}",
            )

        selected = sorted(
            analysis.repositories,
            key=lambda item: item.priority_score,
            reverse=True,
        )[: max(5, min(research_limit, len(analysis.repositories)))]
        try:
            researched = self._research(selected)
            self._merge_research(analysis, researched)
        except Exception as exc:
            analysis.error = (
                f"一手资料研究不可用，已保留 GitHub 内部分析："
                f"{type(exc).__name__}: {exc}"
            )
        return analysis

    def synthesize_period(
        self,
        period_label: str,
        trend: Dict[str, Any],
        snapshots: List[Dict[str, Any]],
    ) -> Optional[Dict[str, List[str]]]:
        """Turn accumulated daily evidence into a nontechnical period review."""
        if not self.api_key or not snapshots:
            return None
        daily_evidence = []
        for snapshot in snapshots:
            analysis = snapshot.get("industry_analysis", {})
            daily_evidence.append(
                {
                    "date": snapshot.get("date"),
                    "key_judgments": analysis.get("key_judgments", []),
                    "hot_characteristics": analysis.get("hot_characteristics", []),
                    "product_business_signals": analysis.get(
                        "product_business_signals", []
                    ),
                    "watch_next": analysis.get("watch_next", []),
                    "repositories": analysis.get("repositories", []),
                }
            )
        instructions = (
            "你是面向 AI 行业从业者的周期情报分析师。根据多日标准化行业分析与确定性统计，"
            "形成简体中文复盘。明确区分事实、开发者关注信号与推断；不得把 GitHub 热度"
            "写成收入、融资或市场采用。重点说明研究方向变化、目标客户需求、产品机会、"
            "竞争格局、商业化信号、风险和下一周期需要验证的问题。"
            "若覆盖天数不足，应降低措辞强度并明确这是初步信号。不要讨论编程语言或实现细节。"
        )
        source = {
            "period": period_label,
            "trend_statistics": trend,
            "daily_evidence": daily_evidence,
        }
        result = self._structured_request(
            model=self.research_model,
            instructions=instructions,
            source=source,
            schema=PERIODIC_SCHEMA,
            schema_name="periodic_industry_synthesis",
        )
        return {
            key: [str(value) for value in result.get(key, [])]
            for key in PERIODIC_SCHEMA["required"]
        }

    def _classify(self, repositories: List[Repository]) -> IndustryAnalysis:
        source = [
            {
                "rank": repo.rank,
                "full_name": repo.full_name,
                "description": repo.description,
                "topics": repo.topics,
                "stars": repo.stars,
                "stars_today": repo.stars_today,
                "is_new_to_our_report": repo.is_new,
                "rank_change": repo.rank_change,
                "streak_days": repo.streak_days,
                "license": repo.license,
                "created_at": repo.created_at,
                "updated_at": repo.updated_at,
                "readme_excerpt": repo.readme_excerpt[:4_000],
            }
            for repo in repositories
        ]
        instructions = (
            "你是面向 AI 行业从业者的产品与商业情报分析师，不是程序员资讯编辑。"
            "用简体中文分析所有项目，即使项目并非 AI，也要说明它对 AI 行业是否相关。"
            "重点回答：为谁、解决什么问题、产品形态、为何现在受关注、商业化信号、"
            "值得注意的技术会改变什么。不要解释编程语言、代码或实现步骤。"
            "GitHub 热度只能称为开发者关注信号，不能推断收入、融资或市场采用。"
            "没有证据时明确写未知。industry_direction 使用稳定、可跨天聚合的短标签；"
            "priority_score 综合 AI 相关性、产品商业影响、技术新颖性和关注度。"
        )
        result = self._structured_request(
            model=self.model,
            instructions=instructions,
            source=source,
            schema=CLASSIFICATION_SCHEMA,
            schema_name="industry_classification",
        )
        repositories_result = [
            RepoInsight.from_dict(item) for item in result["repositories"]
        ]
        expected = {repo.full_name for repo in repositories}
        actual = {repo.full_name for repo in repositories_result}
        if actual != expected or len(repositories_result) != len(repositories):
            raise ValueError("行业分类返回的仓库集合与输入不一致")
        return IndustryAnalysis(
            key_judgments=[str(v) for v in result["key_judgments"]],
            hot_characteristics=[str(v) for v in result["hot_characteristics"]],
            product_business_signals=[
                str(v) for v in result["product_business_signals"]
            ],
            watch_next=[str(v) for v in result["watch_next"]],
            repositories=repositories_result,
        )

    def _research(self, selected: List[RepoInsight]) -> Dict[str, Any]:
        source = [item.to_dict() for item in selected]
        instructions = (
            "你是严谨的 AI 行业研究员。对每个项目使用网页检索核实其官网、项目方正式资料、"
            "论文或研究机构页面，只采用一手来源，不采用新闻、社交媒体、聚合站或搜索摘要。"
            "用非技术读者能理解的中文更新关键判断。技术部分只解释：它是什么、过去为何难、"
            "现在改变了什么、可能影响谁。不得把 GitHub 热度推断为商业成功。"
            "每个项目尽量提供 1–3 个 HTTPS 一手来源；找不到时 evidence 为空并降低置信度。"
        )
        return self._structured_request(
            model=self.research_model,
            instructions=instructions,
            source=source,
            schema=RESEARCH_SCHEMA,
            schema_name="official_source_research",
            tools=[{"type": "web_search"}],
        )

    @staticmethod
    def _merge_research(
        analysis: IndustryAnalysis,
        researched: Dict[str, Any],
    ) -> None:
        insight_map = {item.full_name: item for item in analysis.repositories}
        for value in researched.get("repositories", []):
            insight = insight_map.get(str(value.get("full_name", "")))
            if not insight:
                continue
            evidence = [
                Evidence.from_dict(item)
                for item in value.get("evidence", [])
                if re.match(r"^https://", str(item.get("url", "")))
            ]
            for field_name in [
                "one_line_summary",
                "why_now",
                "noteworthy_technology",
                "technology_impact",
                "commercialization_signal",
                "maturity",
                "risks",
                "confidence",
            ]:
                if value.get(field_name):
                    setattr(insight, field_name, str(value[field_name]))
            insight.evidence = evidence
            insight.deep_researched = bool(evidence)

    def _structured_request(
        self,
        *,
        model: str,
        instructions: str,
        source: Any,
        schema: Dict[str, Any],
        schema_name: str,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": model,
            "reasoning": {"effort": "low"},
            "instructions": instructions,
            "input": json.dumps(source, ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        if tools:
            payload["tools"] = tools
        body = self.http.request(
            "https://api.openai.com/v1/responses",
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        response = json.loads(body.decode("utf-8"))
        return json.loads(self._extract_output_text(response))

    @staticmethod
    def _extract_output_text(response: Dict[str, Any]) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        texts: List[str] = []
        for output in response.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and isinstance(
                    content.get("text"), str
                ):
                    texts.append(content["text"])
        if not texts:
            raise ValueError("Responses API 没有返回 output_text")
        return "".join(texts)
