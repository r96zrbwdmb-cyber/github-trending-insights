from __future__ import annotations

import json
import time
from base64 import b64decode
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .models import AIAnalysis, RepoInsight, Repository
from .parser import parse_trending_html

USER_AGENT = "github-trending-insights/0.1"


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
            repository.license = license_data.get("spdx_id") or license_data.get("name") or ""
            repository.created_at = metadata.get("created_at") or ""
            repository.updated_at = metadata.get("updated_at") or ""
            repository.open_issues = int(metadata.get("open_issues_count") or 0)
            repository.default_branch = metadata.get("default_branch") or ""
            repository.readme_excerpt = self._fetch_readme(slug)
        except Exception as exc:  # one bad repository must not abort the daily report
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


ANALYSIS_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["daily_insights", "repositories"],
    "properties": {
        "daily_insights": {
            "type": "array",
            "minItems": 5,
            "maxItems": 10,
            "items": {"type": "string"},
        },
        "repositories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "full_name",
                    "technology_summary",
                    "application_domains",
                    "primary_use_cases",
                    "novelty_reason",
                    "adoption_signal",
                    "risks_or_limits",
                ],
                "properties": {
                    "full_name": {"type": "string"},
                    "technology_summary": {"type": "string"},
                    "application_domains": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "primary_use_cases": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "novelty_reason": {"type": "string"},
                    "adoption_signal": {"type": "string"},
                    "risks_or_limits": {"type": "string"},
                },
            },
        },
    },
}


class OpenAIClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-terra",
        http: Optional[HTTPClient] = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.http = http or HTTPClient(retries=2, timeout=90)

    def analyze(self, repositories: List[Repository]) -> AIAnalysis:
        if not self.api_key:
            return AIAnalysis.unavailable("未配置 OPENAI_API_KEY")
        error = ""
        for _ in range(2):
            try:
                result = self._request(repositories)
                analysis = self._validate(result, repositories)
                return analysis
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
        return AIAnalysis.unavailable(f"AI 分析重试后仍失败：{error}")

    def _request(self, repositories: List[Repository]) -> Dict[str, Any]:
        source = [
            {
                "rank": repo.rank,
                "full_name": repo.full_name,
                "description": repo.description,
                "language": repo.language,
                "topics": repo.topics,
                "stars": repo.stars,
                "stars_today": repo.stars_today,
                "is_new_to_our_daily_report": repo.is_new,
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
            "你是谨慎的技术趋势分析师。用简体中文分析给定 GitHub 仓库。"
            "必须区分：仅仅首次出现在本报告、已有技术突然升温、"
            "以及有证据支持的潜在新技术。"
            "不要把首次上榜写成技术首创，不要补造仓库未提供的事实。"
            "adoption_signal 必须引用输入里的排名、Star、"
            "连续上榜或更新时间信号；"
            "risks_or_limits 要覆盖成熟度、许可证或落地限制中最相关的一项。"
        )
        payload = {
            "model": self.model,
            "reasoning": {"effort": "low"},
            "instructions": instructions,
            "input": json.dumps(source, ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "github_trending_analysis",
                    "strict": True,
                    "schema": ANALYSIS_SCHEMA,
                }
            },
        }
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
        text = self._extract_output_text(response)
        return json.loads(text)

    @staticmethod
    def _extract_output_text(response: Dict[str, Any]) -> str:
        if isinstance(response.get("output_text"), str):
            return response["output_text"]
        texts: List[str] = []
        for output in response.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                    texts.append(content["text"])
        if not texts:
            raise ValueError("Responses API 没有返回 output_text")
        return "".join(texts)

    @staticmethod
    def _validate(payload: Dict[str, Any], repositories: List[Repository]) -> AIAnalysis:
        daily = payload.get("daily_insights")
        items = payload.get("repositories")
        if not isinstance(daily, list) or not 5 <= len(daily) <= 10:
            raise ValueError("daily_insights 数量必须为 5–10")
        if not isinstance(items, list):
            raise ValueError("repositories 必须是数组")
        parsed = [RepoInsight.from_dict(item) for item in items]
        expected = {repo.full_name for repo in repositories}
        actual = {repo.full_name for repo in parsed}
        if actual != expected or len(parsed) != len(repositories):
            raise ValueError("AI 返回的仓库集合与输入不一致")
        return AIAnalysis(daily_insights=[str(v) for v in daily], repositories=parsed)
