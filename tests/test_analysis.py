from datetime import date, timedelta
from unittest import TestCase

from trending_report.analysis import apply_history, build_index, summarize_window
from trending_report.models import ANALYSIS_VERSION, Repository


def repo(rank: int, name: str) -> Repository:
    return Repository(rank=rank, full_name=name, url=f"https://github.com/{name}")


def industry_snapshot(value_date: date, themes: list) -> dict:
    projects = []
    for index, theme in enumerate(themes):
        projects.append(
            {
                "full_name": f"owner/{theme}-{index}",
                "industry_direction": theme,
                "target_users": ["企业团队"],
                "product_form": "企业软件",
            }
        )
    return {
        "date": value_date.isoformat(),
        "industry_analysis": {
            "available": True,
            "analysis_version": ANALYSIS_VERSION,
            "repositories": projects,
        },
    }


class AnalysisTests(TestCase):
    def test_history_rank_first_seen_and_streak(self) -> None:
        snapshots = [
            {
                "date": "2026-07-26",
                "repositories": [{"rank": 5, "full_name": "old/project"}],
            },
            {
                "date": "2026-07-27",
                "repositories": [{"rank": 4, "full_name": "old/project"}],
            },
        ]
        repositories = [repo(1, "old/project"), repo(2, "new/project")]
        apply_history(repositories, snapshots, date(2026, 7, 28))
        self.assertEqual(repositories[0].rank_change, 3)
        self.assertEqual(repositories[0].streak_days, 3)
        self.assertTrue(repositories[1].is_new)

    def test_one_day_window_is_marked_as_observation_period(self) -> None:
        end = date(2026, 7, 28)
        result = summarize_window(
            [industry_snapshot(end, ["企业智能体"])],
            end,
            7,
        )
        self.assertEqual(result["observed_days"], 1)
        self.assertEqual(result["status"], "insufficient")
        self.assertEqual(result["emerging"][0]["theme"], "企业智能体")

    def test_seven_day_window_detects_acceleration_and_cooling(self) -> None:
        end = date(2026, 7, 28)
        snapshots = []
        for offset in range(7):
            current = end - timedelta(days=6 - offset)
            themes = ["旧方向"] if offset < 3 else ["企业智能体", "企业智能体"]
            snapshots.append(industry_snapshot(current, themes))
        result = summarize_window(snapshots, end, 7)
        self.assertEqual(result["status"], "complete")
        self.assertIn(
            "企业智能体",
            [item["theme"] for item in result["accelerating"]],
        )
        self.assertIn("旧方向", [item["theme"] for item in result["cooling"]])

    def test_thirty_day_window_requires_twenty_valid_days(self) -> None:
        end = date(2026, 7, 28)
        snapshots = [
            industry_snapshot(end - timedelta(days=value), ["模型工具"])
            for value in range(19)
        ]
        self.assertEqual(
            summarize_window(snapshots, end, 30)["status"],
            "insufficient",
        )
        snapshots.append(industry_snapshot(end - timedelta(days=19), ["模型工具"]))
        self.assertEqual(summarize_window(snapshots, end, 30)["status"], "complete")

    def test_legacy_analysis_is_excluded(self) -> None:
        legacy = {
            "date": "2026-07-28",
            "ai_analysis": {"available": True},
        }
        result = summarize_window([legacy], date(2026, 7, 28), 7)
        self.assertEqual(result["observed_days"], 0)

    def test_backfill_does_not_replace_latest_index_state(self) -> None:
        existing = {
            "last_successful_run": "2026-07-28",
            "repositories": {
                "old/project": {
                    "first_seen": "2026-07-27",
                    "last_seen": "2026-07-28",
                    "latest_rank": 1,
                    "streak_days": 2,
                }
            },
        }
        result = build_index([repo(9, "old/project")], existing, date(2026, 7, 26))
        record = result["repositories"]["old/project"]
        self.assertEqual(result["last_successful_run"], "2026-07-28")
        self.assertEqual(record["first_seen"], "2026-07-26")
        self.assertEqual(record["latest_rank"], 1)
