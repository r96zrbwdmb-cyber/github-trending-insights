import json
import tempfile
from pathlib import Path
from unittest import TestCase

from trending_report.models import ANALYSIS_VERSION
from trending_report.site import build_site


class SiteTests(TestCase):
    def test_builds_two_tab_page_and_historical_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source_site = Path(__file__).parents[1] / "site"
            root.joinpath("site").mkdir()
            for name in ["index.html", "app.js", "styles.css"]:
                root.joinpath("site", name).write_text(
                    source_site.joinpath(name).read_text(encoding="utf-8"),
                    encoding="utf-8",
                )
            root.joinpath("data/producthunt").mkdir(parents=True)
            root.joinpath("data/2026-08-02.json").write_text(
                json.dumps(
                    {
                        "date": "2026-08-02",
                        "repositories": [],
                        "industry_analysis": {
                            "available": True,
                            "analysis_version": ANALYSIS_VERSION,
                            "repositories": [],
                            "key_judgments": ["本周智能体产品持续受到关注"],
                            "watch_next": ["观察企业采用"],
                        },
                    }
                )
            )
            root.joinpath("data/producthunt/2026-08-02.json").write_text(
                json.dumps(
                    {
                        "date": "2026-08-02",
                        "products": [{"slug": "fixture"}],
                        "analysis": {
                            "products": [
                                {
                                    "slug": "fixture",
                                    "category": "AI 办公",
                                    "pricing_model": "订阅",
                                    "target_customers": ["企业团队"],
                                }
                            ],
                            "key_judgments": ["企业 AI 工具增加"],
                            "new_product_forms": ["可交付任务的智能体"],
                        },
                    }
                )
            )
            output = build_site(root)
            page = output.joinpath("index.html").read_text(encoding="utf-8")
            self.assertIn("GitHub Trending", page)
            self.assertIn("Product Hunt", page)
            self.assertNotIn("__SITE_DATA__", page)
            self.assertTrue(
                output.joinpath("data/producthunt/2026-08-02.json").exists()
            )
            self.assertIn('"periods":', page)
            self.assertIn("本周智能体产品持续受到关注", page)
            self.assertIn("AI 办公", page)
            self.assertTrue(
                root.joinpath("data/periods/github/weekly/2026-W31.json").exists()
            )
