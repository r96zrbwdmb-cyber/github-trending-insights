from unittest import TestCase

from trending_report.__main__ import build_parser


class CLITests(TestCase):
    def test_daily_weekly_monthly_and_reanalyze_commands(self) -> None:
        parser = build_parser()
        daily = parser.parse_args(["run", "--date", "2026-07-28", "--no-ai"])
        weekly = parser.parse_args(["weekly", "--end-date", "2026-08-02"])
        monthly = parser.parse_args(["monthly", "--month", "2026-07"])
        reanalyze = parser.parse_args(["reanalyze", "--days", "30"])
        producthunt = parser.parse_args(["producthunt", "--date", "2026-07-28"])
        build_site = parser.parse_args(["build-site"])
        run_all = parser.parse_args(["run-all", "--no-ai"])

        self.assertTrue(daily.no_ai)
        self.assertEqual(weekly.end_date, "2026-08-02")
        self.assertEqual(monthly.month, "2026-07")
        self.assertEqual(reanalyze.days, 30)
        self.assertEqual(producthunt.date, "2026-07-28")
        self.assertEqual(build_site.command, "build-site")
        self.assertTrue(run_all.no_ai)
