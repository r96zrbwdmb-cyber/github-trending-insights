import json
import tempfile
from pathlib import Path
from unittest import TestCase

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
            root.joinpath("data/2026-07-30.json").write_text(
                json.dumps({"date": "2026-07-30", "repositories": []})
            )
            root.joinpath("data/producthunt/2026-07-29.json").write_text(
                json.dumps({"date": "2026-07-29", "products": []})
            )
            output = build_site(root)
            page = output.joinpath("index.html").read_text(encoding="utf-8")
            self.assertIn("GitHub Trending", page)
            self.assertIn("Product Hunt", page)
            self.assertNotIn("__SITE_DATA__", page)
            self.assertTrue(
                output.joinpath("data/producthunt/2026-07-29.json").exists()
            )
