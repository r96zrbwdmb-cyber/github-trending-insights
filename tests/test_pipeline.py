import json
import tempfile
from datetime import date
from pathlib import Path
from unittest import TestCase

from trending_report.models import Repository
from trending_report.pipeline import run


class FakeGitHub:
    def fetch_trending(self, limit: int = 25) -> list:
        return [
            Repository(
                rank=index,
                full_name=f"owner/repo-{index}",
                url=f"https://github.com/owner/repo-{index}",
                language="Python" if index % 2 else "Rust",
                stars=1000 + index,
                stars_today=100 - index,
                topics=["ai"] if index % 2 else ["database"],
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


class PipelineTests(TestCase):
    def test_rule_only_end_to_end_writes_all_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("README.md").write_text("# Test\n", encoding="utf-8")
            report = run(root, date(2026, 7, 28), no_ai=True, github=FakeGitHub())

            self.assertTrue(report.exists())
            text = report.read_text(encoding="utf-8")
            for heading in [
                "## 今日摘要",
                "## 新发现",
                "## 上升最快项目",
                "## 技术 / 领域聚类",
                "## 值得持续观察",
                "## Top 25 简表",
                "## 数据与分析限制",
            ]:
                self.assertIn(heading, text)
            snapshot = json.loads(
                root.joinpath("data/2026-07-28.json").read_text(encoding="utf-8")
            )
            self.assertEqual(snapshot["repository_count"], 25)
            self.assertFalse(snapshot["ai_analysis"]["available"])
            self.assertIn("2026-07-28", root.joinpath("README.md").read_text(encoding="utf-8"))

    def test_invalid_collection_does_not_touch_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "reports" / "2026-07-28.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("keep me", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "停止写入"):
                run(root, date(2026, 7, 28), no_ai=True, github=BrokenGitHub())
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep me")

    def test_backfill_keeps_readme_linked_to_latest_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            root.joinpath("README.md").write_text("# Test\n", encoding="utf-8")
            run(root, date(2026, 7, 28), no_ai=True, github=FakeGitHub())
            run(root, date(2026, 7, 27), no_ai=True, github=FakeGitHub())
            readme = root.joinpath("README.md").read_text(encoding="utf-8")
            self.assertIn("最新日报：[2026-07-28]", readme)
