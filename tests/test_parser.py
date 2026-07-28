from pathlib import Path
from unittest import TestCase

from trending_report.parser import parse_count, parse_trending_html

FIXTURE = Path(__file__).parent / "fixtures" / "trending.html"


class ParserTests(TestCase):
    def test_parse_counts(self) -> None:
        self.assertEqual(parse_count("12.3k"), 12_300)
        self.assertEqual(parse_count("1,234 stars"), 1_234)
        self.assertEqual(parse_count("unknown"), 0)

    def test_parse_trending_cards_in_rank_order(self) -> None:
        repositories = parse_trending_html(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual([repo.full_name for repo in repositories], [
            "alpha/one",
            "beta/two",
            "gamma/three",
        ])
        self.assertEqual(repositories[0].rank, 1)
        self.assertEqual(repositories[0].stars, 12_300)
        self.assertEqual(repositories[0].forks, 1_234)
        self.assertEqual(repositories[0].stars_today, 456)
        self.assertEqual(repositories[2].language, "")

    def test_missing_repository_cards_is_a_hard_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "没有找到"):
            parse_trending_html("<html><body>changed</body></html>")

    def test_limit_is_applied(self) -> None:
        repositories = parse_trending_html(FIXTURE.read_text(encoding="utf-8"), limit=2)
        self.assertEqual(len(repositories), 2)
