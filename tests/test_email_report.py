import json
import tempfile
import unittest
from pathlib import Path

from trending_report.email_report import build_daily_email


class EmailReportTests(unittest.TestCase):
    def test_builds_combined_chinese_email_without_internal_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data" / "producthunt").mkdir(parents=True)
            (root / "data" / "2026-07-30.json").write_text(
                json.dumps(
                    {
                        "date": "2026-07-30",
                        "industry_analysis": {
                            "key_judgments": ["AI 智能体评估正在升温"],
                            "error": "内部分析错误",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (root / "data" / "producthunt" / "2026-07-29.json").write_text(
                json.dumps(
                    {
                        "date": "2026-07-29",
                        "analysis": {
                            "key_judgments": ["企业开始购买 AI 质量保障能力"],
                            "error": "ValueError",
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            subject, body = build_daily_email(root)

            self.assertIn("2026-07-30", subject)
            self.assertIn("AI 智能体评估正在升温", body)
            self.assertIn("企业开始购买 AI 质量保障能力", body)
            self.assertNotIn("ValueError", body)
            self.assertNotIn("内部分析错误", body)


if __name__ == "__main__":
    unittest.main()
