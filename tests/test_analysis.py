from datetime import date
from unittest import TestCase

from trending_report.analysis import apply_history, build_index, summarize_clusters
from trending_report.models import Repository


def repo(rank: int, name: str) -> Repository:
    return Repository(rank=rank, full_name=name, url=f"https://github.com/{name}")


class AnalysisTests(TestCase):
    def test_history_rank_first_seen_and_consecutive_streak(self) -> None:
        snapshots = [
            {
                "date": "2026-07-25",
                "repositories": [{"rank": 3, "full_name": "old/project"}],
            },
            {
                "date": "2026-07-26",
                "repositories": [
                    {"rank": 5, "full_name": "old/project"},
                    {"rank": 2, "full_name": "gap/project"},
                ],
            },
            {
                "date": "2026-07-27",
                "repositories": [{"rank": 4, "full_name": "old/project"}],
            },
        ]
        repositories = [repo(1, "old/project"), repo(2, "new/project"), repo(3, "gap/project")]
        apply_history(repositories, snapshots, date(2026, 7, 28))

        self.assertFalse(repositories[0].is_new)
        self.assertEqual(repositories[0].rank_change, 3)
        self.assertEqual(repositories[0].streak_days, 4)
        self.assertTrue(repositories[1].is_new)
        self.assertEqual(repositories[1].streak_days, 1)
        self.assertFalse(repositories[2].is_new)
        self.assertEqual(repositories[2].streak_days, 1)

    def test_cluster_counts_language_and_topics(self) -> None:
        first = repo(1, "a/a")
        first.language = "Python"
        first.topics = ["ai", "agents"]
        second = repo(2, "b/b")
        second.language = "Python"
        second.topics = ["ai"]
        clusters = dict(summarize_clusters([first, second]))
        self.assertEqual(clusters["语言:Python"], 2)
        self.assertEqual(clusters["主题:ai"], 2)

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
