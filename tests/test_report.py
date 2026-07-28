from datetime import date
from unittest import TestCase

from trending_report.models import Evidence, IndustryAnalysis, RepoInsight, Repository
from trending_report.report import render_daily_report, update_readme


def analysis() -> IndustryAnalysis:
    return IndustryAnalysis(
        key_judgments=["一", "二", "三", "四", "五"],
        hot_characteristics=["企业需求上升"],
        product_business_signals=["出现企业部署方案"],
        watch_next=["验证真实客户采用"],
        repositories=[
            RepoInsight(
                full_name="a/b",
                one_line_summary="企业知识助手",
                industry_direction="企业智能体",
                target_users=["企业团队"],
                problem_solved="信息分散",
                solution="统一知识入口",
                why_now="模型能力改善",
                noteworthy_technology="可验证检索",
                technology_impact="回答可以追溯",
                product_form="企业软件",
                commercialization_signal="提供企业部署",
                maturity="公开测试",
                risks="真实采用待验证",
                ai_relevance="直接相关",
                confidence="高",
                priority_score=90,
                evidence=[
                    Evidence(
                        title="项目官网",
                        url="https://example.com",
                        source_type="official",
                    )
                ],
                deep_researched=True,
            )
        ],
    )


def empty_trend(days: int) -> dict:
    return {
        "window_days": days,
        "observed_days": 0,
        "status": "insufficient",
        "emerging": [],
        "accelerating": [],
        "cooling": [],
        "persistent": [],
        "top_users": [],
        "top_product_forms": [],
    }


class ReportTests(TestCase):
    def test_report_is_for_industry_reader_not_programmer(self) -> None:
        repo = Repository(
            rank=1,
            full_name="a/b",
            url="https://github.com/a/b",
            language="Python",
            stars_today=100,
        )
        text = render_daily_report(
            date(2026, 7, 28),
            [repo],
            analysis(),
            empty_trend(7),
            empty_trend(30),
        )
        for heading in [
            "## 今天最重要的 5 个判断",
            "## 今天的热门有什么特点",
            "## 重点方向与项目",
            "## 特别值得注意的技术",
            "## 产品与商业动态",
            "## 过去 7 天 / 30 天发生了什么变化",
            "## 接下来值得关注",
            "## 全榜附录",
        ]:
            self.assertIn(heading, text)
        self.assertIn("面向谁", text)
        self.assertIn("解决什么问题", text)
        self.assertNotIn("Python", text)
        self.assertNotIn("| 语言 |", text)

    def test_unavailable_analysis_is_clearly_pending(self) -> None:
        repo = Repository(rank=1, full_name="a/b", url="https://github.com/a/b")
        unavailable = IndustryAnalysis.unavailable([repo], "missing key")
        text = render_daily_report(
            date(2026, 7, 28),
            [repo],
            unavailable,
            empty_trend(7),
            empty_trend(30),
        )
        self.assertIn("行业分析待生成", text)
        self.assertNotIn("技术 / 领域聚类", text)

    def test_readme_links_daily_weekly_monthly(self) -> None:
        result = update_readme(
            "# Test\n",
            date(2026, 7, 28),
            "2026-W31",
            "2026-07",
        )
        self.assertIn("最新日报", result)
        self.assertIn("最新周报", result)
        self.assertIn("最新月报", result)

