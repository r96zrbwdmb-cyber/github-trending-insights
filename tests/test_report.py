from datetime import date
from unittest import TestCase

from trending_report.models import AIAnalysis, Repository
from trending_report.report import render_report, update_readme


class ReportTests(TestCase):
    def test_report_escapes_table_and_explains_ai_degradation(self) -> None:
        repo = Repository(
            rank=1,
            full_name="a/b",
            url="https://github.com/a/b",
            description="x",
            language="C|C++",
            is_new=True,
        )
        text = render_report(
            date(2026, 7, 28),
            [repo],
            AIAnalysis.unavailable("test"),
            [],
        )
        self.assertIn("C\\|C++", text)
        self.assertIn("OpenAI 分析不可用", text)

    def test_readme_marker_is_replaced_without_duplicate(self) -> None:
        first = update_readme("# Title\n", date(2026, 7, 27))
        second = update_readme(first, date(2026, 7, 28))
        self.assertEqual(second.count("<!-- latest-report:start -->"), 1)
        self.assertNotIn("2026-07-27", second)
        self.assertIn("2026-07-28", second)

