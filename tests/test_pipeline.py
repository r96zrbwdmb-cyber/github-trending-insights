import json
import tempfile
from datetime import date, timedelta
from pathlib import Path
from unittest import TestCase

from trending_report.models import ANALYSIS_VERSION, Repository
from trending_report.pipeline import generate_monthly, generate_weekly, run


class FakeGitHub:
    def fetch_trending(self, limit: int = 25) -> list:
        return [
            Repository(
                rank=index,
                full_name=f"owner/repo-{index}",
                url=f"https://github.com/owner/repo-{index}",
                language="Python",
                stars=1000 + index,
                stars_today=100 - index,
                topics=["ai"],
                description=f"Project {index}",
            )
            for index in range(1, 26)
        ]

    def enrich(self, repository: Repository) -> Repository:
        repository.license = "MIT"
        repository.readme_excerpt = "Fixture README"
        return repository


class BrokenGitHub(FakeGitHub):
    def fetch_trending(self, limit: int = 25) -> list:
        return super().fetch_trending(limit)[:2]


def valid_snapshot(value_date: date) -> dict:
    return {
        "date": value_date.isoformat(),
        "repositories": [],
        "industry_analysis": {
            "analysis_version": ANALYSIS_VERSION,
            "available": True,
            "error": "",
            "key_judgments": [f"{value_date} 的判断"],
            "hot_characteristics": [],
            "product_business_signals": [],
            "watch_next": ["观察企业采用"],
            "repositories": [
                {
                    "full_name": f"owner/repo-{value_date.day}",
                    "industry_direction": "企业智能体",
                    "target_users": ["企业团队"],
                    "product_form": "企业软件",
                }
            ],
        },
    }


class PipelineTests(TestCase):
    def test_rule_only_end_to_end_marks_analysis_pending(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("README.md").write_text("# Test\n", encoding="utf-8")
            report = run(root, date(2026, 7, 28), no_ai=True, github=FakeGitHub())
            text = report.read_text(encoding="utf-8")
            self.assertIn("行业分析待生成", text)
            self.assertNotIn("| 语言 |", text)
            snapshot = json.loads(
                root.joinpath("data/2026-07-28.json").read_text(encoding="utf-8")
            )
            self.assertEqual(snapshot["repository_count"], 25)
            self.assertFalse(snapshot["industry_analysis"]["available"])
            self.assertEqual(
                snapshot["industry_analysis"]["analysis_version"],
                ANALYSIS_VERSION,
            )

    def test_invalid_collection_does_not_touch_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "reports" / "2026-07-28.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("keep me", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "停止写入"):
                run(root, date(2026, 7, 28), no_ai=True, github=BrokenGitHub())
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep me")

    def test_weekly_and_monthly_reports_use_observation_thresholds(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            data_dir.mkdir()
            end = date(2026, 7, 31)
            for offset in range(20):
                value = valid_snapshot(end - timedelta(days=offset))
                data_dir.joinpath(f"{value['date']}.json").write_text(
                    json.dumps(value, ensure_ascii=False),
                    encoding="utf-8",
                )
            weekly = generate_weekly(root, end)
            monthly = generate_monthly(root, "2026-07")
            self.assertIn("完整复盘", weekly.read_text(encoding="utf-8"))
            self.assertIn("完整复盘", monthly.read_text(encoding="utf-8"))
            self.assertTrue(root.joinpath("reports/index.md").exists())

    def test_monday_and_month_start_create_periodic_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("README.md").write_text("# Test\n", encoding="utf-8")
            run(root, date(2026, 6, 1), no_ai=True, github=FakeGitHub())
            self.assertTrue(any(root.joinpath("reports/weekly").glob("*.md")))
            self.assertTrue(root.joinpath("reports/monthly/2026-05.md").exists())

    def test_backfill_keeps_readme_linked_to_latest_daily(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("README.md").write_text("# Test\n", encoding="utf-8")
            run(root, date(2026, 7, 28), no_ai=True, github=FakeGitHub())
            run(root, date(2026, 7, 27), no_ai=True, github=FakeGitHub())
            readme = root.joinpath("README.md").read_text(encoding="utf-8")
            self.assertIn("最新日报：[2026-07-28]", readme)
