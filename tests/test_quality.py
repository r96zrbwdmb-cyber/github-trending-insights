import unittest

from trending_report.fallback import build_fallback_analysis
from trending_report.models import Repository
from trending_report.producthunt import (
    Product,
    _fallback_analysis,
    product_analysis_quality_errors,
)
from trending_report.quality import github_analysis_quality_errors


class QualityGateTests(unittest.TestCase):
    def test_github_fallback_is_specific_and_consistent(self) -> None:
        repositories = [
            Repository(1, "org/weather", "https://github.com/org/weather",
                       description="AI weather forecast model", stars_today=100),
            Repository(2, "org/code-agent", "https://github.com/org/code-agent",
                       description="Coding agent for long running tasks", stars_today=90),
            Repository(3, "org/voice", "https://github.com/org/voice",
                       description="Real-time voice assistant", stars_today=80),
            Repository(4, "org/security", "https://github.com/org/security",
                       description="Agent identity permissions and sandbox", stars_today=70),
        ]
        analysis = build_fallback_analysis(repositories, "fixture")
        self.assertEqual(github_analysis_quality_errors(analysis, 4), [])
        self.assertEqual(len({tuple(item.practical_benefits)
                              for item in analysis.repositories}), 4)
        self.assertIn("4/4", analysis.key_judgments[0])

    def test_github_fallback_distinguishes_projects_in_same_broad_theme(self) -> None:
        repositories = [
            Repository(1, "org/context", "https://github.com/org/context",
                       description="Context graphs and provenance for accountable AI"),
            Repository(2, "org/roles", "https://github.com/org/roles",
                       description="A complete AI agency with specialized expert roles"),
            Repository(3, "org/manager", "https://github.com/org/manager",
                       description="An app to manage agents at work"),
            Repository(4, "org/learner", "https://github.com/org/learner",
                       description="A self-improving agent for long-running autonomous tasks"),
        ]
        analysis = build_fallback_analysis(repositories, "fixture")
        self.assertEqual(github_analysis_quality_errors(analysis, 4), [])
        self.assertEqual(
            len({tuple(item.practical_benefits) for item in analysis.repositories}),
            4,
        )
        self.assertEqual(
            len({item.problem_solved for item in analysis.repositories}), 4
        )

    def test_product_fallback_rejects_template_repetition(self) -> None:
        products = [
            Product(str(i), i, f"p-{i}", f"Product {i}", "Same", "Same",
                    "https://example.com", "https://example.com", 1, 1, "", "")
            for i in range(1, 7)
        ]
        analysis = _fallback_analysis(products)
        self.assertEqual(product_analysis_quality_errors(analysis, 6), [])
        self.assertEqual(len({tuple(item["target_customers"])
                              for item in analysis["products"]}), 6)


if __name__ == "__main__":
    unittest.main()
