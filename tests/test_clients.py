import json
from unittest import TestCase, mock
from urllib.error import HTTPError, URLError

from trending_report.clients import (
    CLASSIFICATION_SCHEMA,
    PERIODIC_SCHEMA,
    GitHubClient,
    HTTPClient,
    OpenAIClient,
)
from trending_report.models import Repository


class FakeHTTP:
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls = []

    def request(self, *args: object, **kwargs: object) -> bytes:
        self.calls.append({"args": args, "kwargs": kwargs})
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return json.dumps(value).encode()


def repository(name: str = "alpha/one") -> Repository:
    return Repository(rank=1, full_name=name, url=f"https://github.com/{name}")


def project_value(name: str = "alpha/one") -> dict:
    return {
        "full_name": name,
        "one_line_summary": "面向企业的智能知识助手",
        "industry_direction": "企业智能体",
        "target_users": ["企业知识团队"],
        "problem_solved": "内部信息分散",
        "solution": "统一检索和任务执行",
        "why_now": "模型能力和部署成本改善",
        "noteworthy_technology": "可验证检索",
        "technology_impact": "降低错误回答风险",
        "product_form": "企业软件",
        "commercialization_signal": "提供企业部署方案",
        "maturity": "早期产品",
        "risks": "效果依赖内部数据质量",
        "ai_relevance": "直接服务 AI 应用落地",
        "plain_language_explanation": "像给企业资料配一个会查证的智能助理",
        "scenario_examples": ["客服查找政策", "销售准备客户资料"],
        "practical_benefits": ["减少查找时间", "降低错误回答"],
        "industry_implications": "企业 AI 从问答转向可执行工作流",
        "who_should_care": "企业产品负责人和知识管理团队",
        "validation_signals": ["是否出现真实客户案例", "是否持续活跃"],
        "claim_checks": [
            {
                "claim": "项目进入日榜",
                "claim_type": "已验证事实",
                "source_kind": "github_metadata",
                "source_excerpt": "",
            },
            {
                "claim": "提供企业知识助手",
                "claim_type": "项目方说法",
                "source_kind": "readme",
                "source_excerpt": "",
            },
            {
                "claim": "可能推动企业工作流自动化",
                "claim_type": "分析判断",
                "source_kind": "analysis",
                "source_excerpt": "",
            },
        ],
        "confidence": "中",
        "priority_score": 90,
    }


def classification() -> dict:
    return {
        "key_judgments": ["判断一", "判断二", "判断三", "判断四", "判断五"],
        "hot_characteristics": ["企业需求增加", "产品化增强"],
        "product_business_signals": ["开始面向企业部署", "竞争转向工作流"],
        "watch_next": ["验证实际客户采用", "观察持续上榜"],
        "repositories": [project_value()],
    }


def response(value: dict) -> dict:
    return {
        "output": [
            {"content": [{"type": "output_text", "text": json.dumps(value)}]}
        ]
    }


def github_response(value: dict) -> dict:
    return {"choices": [{"message": {"content": json.dumps(value)}}]}


class OpenAIClientTests(TestCase):
    def test_two_stage_analysis_merges_official_research(self) -> None:
        research = {
            "repositories": [
                {
                    "full_name": "alpha/one",
                    "one_line_summary": "经官方资料核实的企业助手",
                    "why_now": "企业正在寻找可控部署方案",
                    "noteworthy_technology": "可验证检索",
                    "technology_impact": "让回答能追溯来源",
                    "commercialization_signal": "官网提供企业版",
                    "maturity": "公开测试",
                    "risks": "仍需验证真实采用",
                    "confidence": "高",
                    "evidence": [
                        {
                            "title": "项目官网",
                            "url": "https://example.com/official",
                            "source_type": "official",
                        }
                    ],
                }
            ]
        }
        http = FakeHTTP([response(classification()), response(research)])
        result = OpenAIClient("secret", http=http).analyze([repository()])
        self.assertTrue(result.available)
        self.assertTrue(result.repositories[0].deep_researched)
        self.assertEqual(result.repositories[0].confidence, "高")
        second_payload = json.loads(http.calls[1]["kwargs"]["data"])
        self.assertEqual(second_payload["tools"], [{"type": "web_search"}])

    def test_research_failure_keeps_classification(self) -> None:
        http = FakeHTTP([response(classification()), RuntimeError("search down")])
        result = OpenAIClient("secret", http=http).analyze([repository()])
        self.assertTrue(result.available)
        self.assertIn("一手资料研究不可用", result.error)
        self.assertFalse(result.repositories[0].deep_researched)

    def test_invalid_classification_retries_then_degrades(self) -> None:
        invalid = {"output_text": '{"key_judgments":[],"repositories":[]}'}
        http = FakeHTTP([invalid, invalid])
        result = OpenAIClient("secret", http=http).analyze([repository()])
        self.assertTrue(result.available)
        self.assertIn("模型不可用", result.error)
        self.assertEqual(result.repositories[0].confidence, "低")
        self.assertEqual(len(http.calls), 2)

    def test_missing_key_returns_project_placeholders(self) -> None:
        http = FakeHTTP([])
        result = OpenAIClient("", http=http).analyze([repository()])
        self.assertFalse(result.available)
        self.assertEqual(result.repositories[0].target_users, ["待分析"])
        self.assertEqual(len(http.calls), 0)

    def test_schema_requires_nontechnical_industry_fields(self) -> None:
        repo_schema = CLASSIFICATION_SCHEMA["properties"]["repositories"]["items"]
        required = set(repo_schema["required"])
        self.assertIn("target_users", required)
        self.assertIn("problem_solved", required)
        self.assertIn("commercialization_signal", required)
        self.assertIn("plain_language_explanation", required)
        self.assertIn("scenario_examples", required)
        self.assertIn("practical_benefits", required)
        self.assertIn("industry_implications", required)
        self.assertIn("claim_checks", required)
        self.assertNotIn("language", required)

    def test_periodic_synthesis_uses_research_model(self) -> None:
        synthesis = {
            key: [f"{key}判断"] for key in PERIODIC_SCHEMA["required"]
        }
        http = FakeHTTP([response(synthesis)])
        client = OpenAIClient("secret", research_model="research-model", http=http)
        result = client.synthesize_period(
            "2026-W31",
            {"observed_days": 5},
            [
                {
                    "date": "2026-07-28",
                    "industry_analysis": classification(),
                }
            ],
        )
        self.assertEqual(result["product_opportunities"], ["product_opportunities判断"])
        payload = json.loads(http.calls[0]["kwargs"]["data"])
        self.assertEqual(payload["model"], "research-model")

    def test_periodic_synthesis_without_key_is_skipped(self) -> None:
        http = FakeHTTP([])
        result = OpenAIClient("", http=http).synthesize_period(
            "2026-W31", {"observed_days": 1}, [{}]
        )
        self.assertIsNone(result)
        self.assertEqual(http.calls, [])

    def test_github_models_uses_free_chat_completions_api(self) -> None:
        http = FakeHTTP([github_response(classification())])
        result = OpenAIClient(
            "github-token",
            model="openai/gpt-4.1-mini",
            research_model="openai/gpt-4.1-mini",
            provider="github",
            http=http,
        ).analyze([repository()])

        self.assertTrue(result.available)
        self.assertTrue(result.repositories[0].deep_researched)
        self.assertIn("免费模式", result.error)
        checks = result.repositories[0].claim_checks
        self.assertEqual(checks[0].verification_status, "结构化数据核对")
        self.assertEqual(checks[1].claim_type, "证据不足")
        self.assertIn("models.github.ai", http.calls[0]["args"][0])
        payload = json.loads(http.calls[0]["kwargs"]["data"])
        self.assertEqual(payload["model"], "openai/gpt-4.1-mini")
        self.assertEqual(payload["response_format"]["type"], "json_schema")


class HTTPClientTests(TestCase):
    @mock.patch("trending_report.clients.time.sleep", return_value=None)
    @mock.patch("trending_report.clients.urlopen")
    def test_rate_limit_retries(self, mocked_urlopen: mock.Mock, _: mock.Mock) -> None:
        rate_limit = HTTPError("https://example.test", 429, "limited", {}, None)
        response_value = mock.MagicMock()
        response_value.__enter__.return_value.read.return_value = b"ok"
        mocked_urlopen.side_effect = [rate_limit, response_value]
        result = HTTPClient(retries=2).request("https://example.test")
        self.assertEqual(result, b"ok")
        self.assertEqual(mocked_urlopen.call_count, 2)

    @mock.patch("trending_report.clients.time.sleep", return_value=None)
    @mock.patch("trending_report.clients.urlopen")
    def test_timeout_exhausts_retries(
        self,
        mocked_urlopen: mock.Mock,
        _: mock.Mock,
    ) -> None:
        mocked_urlopen.side_effect = URLError("timeout")
        with self.assertRaisesRegex(RuntimeError, "请求失败"):
            HTTPClient(retries=2).request("https://example.test")


class StubGitHub(GitHubClient):
    def _json(self, url: str) -> dict:
        if url.endswith("/readme"):
            raise RuntimeError("README missing")
        return {
            "description": "API description",
            "language": "Python",
            "stargazers_count": 100,
            "forks_count": 10,
            "topics": ["agents"],
            "license": None,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-07-28T00:00:00Z",
            "open_issues_count": 3,
            "default_branch": "main",
        }


class GitHubClientTests(TestCase):
    def test_missing_readme_does_not_discard_repository_metadata(self) -> None:
        value = StubGitHub().enrich(repository())
        self.assertEqual(value.description, "API description")
        self.assertEqual(value.readme_excerpt, "")

    def test_metadata_failure_hides_response_details(self) -> None:
        client = GitHubClient(http=FakeHTTP([RuntimeError("secret response")]))
        value = client.enrich(repository())
        self.assertIn("metadata unavailable", value.metadata_error)
        self.assertNotIn("secret response", value.metadata_error)
