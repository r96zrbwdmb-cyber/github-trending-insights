import json
import tempfile
from datetime import date, datetime
from pathlib import Path
from unittest import TestCase
from zoneinfo import ZoneInfo

from trending_report.pipeline import run_producthunt
from trending_report.producthunt import (
    OfficialSiteReader,
    Product,
    ProductHuntClient,
    day_bounds,
    latest_complete_day,
    summarize_product_history,
)


def node(rank: int) -> dict:
    return {
        "id": str(rank),
        "dailyRank": rank,
        "slug": f"product-{rank}",
        "name": f"Product {rank}",
        "tagline": f"Useful product {rank}",
        "description": "Helps teams finish routine work",
        "url": f"https://www.producthunt.com/posts/product-{rank}",
        "website": f"https://product-{rank}.example",
        "votesCount": 100 - rank,
        "commentsCount": rank,
        "createdAt": "2026-07-29T08:00:00Z",
        "featuredAt": "2026-07-29T08:00:00Z",
        "thumbnail": {"url": "https://example.com/image.png"},
        "topics": {"nodes": [{"name": "Artificial Intelligence", "slug": "ai"}]},
        "makers": [{"name": "Maker", "username": "maker"}],
        "productLinks": [],
    }


class FakeHTTP:
    def __init__(self, value: dict) -> None:
        self.value = value
        self.calls = []

    def request(self, *args: object, **kwargs: object) -> bytes:
        self.calls.append((args, kwargs))
        return json.dumps(self.value).encode()


class ProductHuntClientTests(TestCase):
    def test_uses_official_daily_rank_and_top_15(self) -> None:
        values = [node(index) for index in range(20, 0, -1)]
        http = FakeHTTP({"data": {"posts": {"nodes": values}}})
        products = ProductHuntClient("secret", http=http).fetch_daily(
            date(2026, 7, 29)
        )
        self.assertEqual([item.rank for item in products], list(range(1, 16)))
        payload = json.loads(http.calls[0][1]["data"])
        self.assertEqual(payload["variables"]["after"][:10], "2026-07-29")
        self.assertIn("order: RANKING", payload["query"])
        self.assertIn("Bearer secret", http.calls[0][1]["headers"]["Authorization"])

    def test_missing_token_stops_before_request(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "PRODUCT_HUNT_TOKEN"):
            ProductHuntClient("").fetch_daily(date(2026, 7, 29))

    def test_token_whitespace_is_removed_before_header(self) -> None:
        http = FakeHTTP({"data": {"posts": {"nodes": [node(1)]}}})
        ProductHuntClient("  secret-token\n", http=http).fetch_daily(
            date(2026, 7, 29)
        )
        self.assertEqual(
            http.calls[0][1]["headers"]["Authorization"],
            "Bearer secret-token",
        )

    def test_pacific_day_handles_daylight_saving(self) -> None:
        after, before = day_bounds(date(2026, 7, 29))
        self.assertIn("-07:00", after)
        self.assertIn("-07:00", before)
        now = datetime(2026, 7, 30, 9, tzinfo=ZoneInfo("Asia/Shanghai"))
        self.assertEqual(latest_complete_day(now), date(2026, 7, 28))


class FakeProductHunt:
    def fetch_daily(self, report_date: date, limit: int = 15) -> list:
        return [
            ProductHuntClient._product(node(index))
            for index in range(1, limit + 1)
        ]


class NoopReader(OfficialSiteReader):
    def enrich(self, product: Product) -> Product:
        return product


class ProductHuntPipelineTests(TestCase):
    def test_end_to_end_fallback_writes_report_and_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = run_producthunt(
                root,
                date(2026, 7, 29),
                producthunt=FakeProductHunt(),
                reader=NoopReader(),
                openai=None,
            )
            text = report.read_text(encoding="utf-8")
            self.assertIn("卖什么", text)
            self.assertIn("怎么收费", text)
            snapshot = json.loads(
                root.joinpath("data/producthunt/2026-07-29.json").read_text()
            )
            self.assertEqual(snapshot["product_count"], 15)
            self.assertEqual(snapshot["trend_7d"]["observed_days"], 1)

    def test_history_reports_actual_observed_days(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            for value in ["2026-07-27", "2026-07-29"]:
                data.joinpath(f"{value}.json").write_text(
                    json.dumps(
                        {
                            "date": value,
                            "products": [{"slug": value}],
                            "analysis": {
                                "products": [
                                    {
                                        "category": "AI",
                                        "pricing_model": "订阅",
                                        "target_customers": ["团队"],
                                    }
                                ]
                            },
                        }
                    )
                )
            trend = summarize_product_history(data, date(2026, 7, 29), 7)
            self.assertEqual(trend["observed_days"], 2)
            self.assertEqual(trend["status"], "observing")
