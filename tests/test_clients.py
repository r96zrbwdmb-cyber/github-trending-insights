import json
from unittest import TestCase, mock
from urllib.error import HTTPError, URLError

from trending_report.clients import ANALYSIS_SCHEMA, GitHubClient, HTTPClient, OpenAIClient
from trending_report.models import Repository


class FakeHTTP:
    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls = 0

    def request(self, *args: object, **kwargs: object) -> bytes:
        self.calls += 1
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return json.dumps(value).encode()


def repository() -> Repository:
    return Repository(rank=1, full_name="alpha/one", url="https://github.com/alpha/one")


def valid_analysis() -> dict:
    return {
        "daily_insights": ["一", "二", "三", "四", "五"],
        "repositories": [
            {
                "full_name": "alpha/one",
                "technology_summary": "技术",
                "application_domains": ["开发工具"],
                "primary_use_cases": ["编码"],
                "novelty_reason": "首次收录不等于新技术",
                "adoption_signal": "榜单第 1",
                "risks_or_limits": "成熟度待验证",
            }
        ],
    }


class OpenAIClientTests(TestCase):
    def test_extracts_structured_response(self) -> None:
        response = {
            "output": [
                {"content": [{"type": "output_text", "text": json.dumps(valid_analysis())}]}
            ]
        }
        client = OpenAIClient("secret", http=FakeHTTP([response]))
        result = client.analyze([repository()])
        self.assertTrue(result.available)
        self.assertEqual(result.repositories[0].application_domains, ["开发工具"])

    def test_invalid_output_retries_then_degrades(self) -> None:
        invalid = {"output_text": '{"daily_insights":[],"repositories":[]}'}
        http = FakeHTTP([invalid, invalid])
        result = OpenAIClient("secret", http=http).analyze([repository()])
        self.assertFalse(result.available)
        self.assertEqual(http.calls, 2)
        self.assertIn("重试后仍失败", result.error)

    def test_missing_key_degrades_without_http(self) -> None:
        http = FakeHTTP([])
        result = OpenAIClient("", http=http).analyze([repository()])
        self.assertFalse(result.available)
        self.assertEqual(http.calls, 0)

    def test_schema_requires_all_expected_analysis_fields(self) -> None:
        repo_schema = ANALYSIS_SCHEMA["properties"]["repositories"]["items"]
        self.assertTrue(repo_schema["additionalProperties"] is False)
        self.assertEqual(
            set(repo_schema["required"]),
            set(repo_schema["properties"]),
        )


class HTTPClientTests(TestCase):
    @mock.patch("trending_report.clients.time.sleep", return_value=None)
    @mock.patch("trending_report.clients.urlopen")
    def test_rate_limit_retries(self, mocked_urlopen: mock.Mock, _: mock.Mock) -> None:
        rate_limit = HTTPError("https://example.test", 429, "limited", {}, None)
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = b"ok"
        mocked_urlopen.side_effect = [rate_limit, response]
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
        self.assertEqual(value.topics, ["agents"])
        self.assertEqual(value.readme_excerpt, "")
        self.assertEqual(value.metadata_error, "")

    def test_metadata_failure_is_recorded_without_secret_details(self) -> None:
        client = GitHubClient(http=FakeHTTP([RuntimeError("secret response")]))
        value = client.enrich(repository())
        self.assertIn("metadata unavailable", value.metadata_error)
        self.assertNotIn("secret response", value.metadata_error)
