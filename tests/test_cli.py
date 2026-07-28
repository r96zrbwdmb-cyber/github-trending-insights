from unittest import TestCase

from trending_report.__main__ import build_parser


class CLITests(TestCase):
    def test_daily_weekly_monthly_and_reanalyze_commands(self) -> None:
        parser = build_parser()
        daily = parser.parse_args(["run", "--date", "2026-07-28", "--no-ai"])
        weekly = parser.parse_args(["weekly", "--end-date", "2026-08-02"])
        monthly = parser.parse_args(["monthly", "--month", "2026-07"])
        reanalyze = parser.parse_args(["reanalyze", "--days", "30"])

        self.assertTrue(daily.no_ai)
        self.assertEqual(weekly.end_date, "2026-08-02")
        self.assertEqual(monthly.month, "2026-07")
        self.assertEqual(reanalyze.days, 30)
