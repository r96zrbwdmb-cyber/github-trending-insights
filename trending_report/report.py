from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from .models import IndustryAnalysis, RepoInsight, Repository


def _escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _trend_names(items: List[Dict[str, object]]) -> str:
    return "、".join(str(item["theme"]) for item in items) or "尚无可靠结论"


def _render_window(title: str, trend: Dict[str, object]) -> List[str]:
    observed = int(trend["observed_days"])
    window = int(trend["window_days"])
    lines = [f"### {title}", ""]
    if not observed:
        return lines + ["- 尚无带行业分析的有效历史数据。"]
    coverage = f"有效观察 {observed}/{window} 天"
    if trend["status"] != "complete":
        coverage += "，仍处于观察期，以下信号不代表稳定趋势"
    lines.extend(
        [
            f"- **覆盖范围：** {coverage}。",
            f"- **新出现方向：** {_trend_names(trend['emerging'])}。",
            f"- **正在增强：** {_trend_names(trend['accelerating'])}。",
            f"- **持续受到关注：** {_trend_names(trend['persistent'])}。",
            f"- **可能降温：** {_trend_names(trend['cooling'])}。",
        ]
    )
    return lines


def render_daily_report(
    report_date: date,
    repositories: List[Repository],
    analysis: IndustryAnalysis,
    trend_7d: Dict[str, object],
    trend_30d: Dict[str, object],
) -> str:
    repo_map = {repo.full_name: repo for repo in repositories}
    priority = sorted(
        analysis.repositories,
        key=lambda item: item.priority_score,
        reverse=True,
    )
    grouped: Dict[str, List[RepoInsight]] = defaultdict(list)
    for insight in priority:
        grouped[insight.industry_direction].append(insight)

    lines = [
        f"# AI 行业情报简报 · {report_date.isoformat()}",
        "",
        "> 约 5 分钟阅读。数据来自 GitHub Trending 全语言日榜；"
        "它代表开发者关注度，不等同于市场采用、收入、融资或研究突破。",
        "",
        "## 今天最重要的 5 个判断",
        "",
    ]
    if analysis.available:
        lines.extend(f"{index}. {value}" for index, value in enumerate(
            analysis.key_judgments, 1
        ))
    else:
        lines.extend(
            [
                f"> ⚠️ 行业分析待生成：{analysis.error}",
                "",
                "今天的原始榜单已经保存，但在完成 AI 行业分析前，"
                "不据此推断研究方向、产品机会或商业变化。",
            ]
        )

    lines.extend(["", "## 今天的热门有什么特点", ""])
    if analysis.hot_characteristics:
        lines.extend(f"- {value}" for value in analysis.hot_characteristics)
    else:
        lines.append("- 行业分析待生成，暂不从项目名称或技术标签推断行业特点。")

    lines.extend(["", "## 重点方向与项目", ""])
    if analysis.available:
        for direction, insights in list(grouped.items())[:6]:
            lines.extend([f"### {direction}", ""])
            for insight in insights[:3]:
                repo = repo_map.get(insight.full_name)
                url = repo.url if repo else f"https://github.com/{insight.full_name}"
                users = "、".join(insight.target_users) or "尚不明确"
                lines.extend(
                    [
                        f"- **[{insight.full_name}]({url})**："
                        f"{insight.one_line_summary}",
                        f"  - **面向谁：** {users}",
                        f"  - **解决什么：** {insight.problem_solved}",
                        f"  - **为什么重要：** {insight.why_now}",
                    ]
                )
                if insight.evidence:
                    sources = "、".join(
                        f"[{item.title}]({item.url})" for item in insight.evidence
                    )
                    lines.append(f"  - **一手资料：** {sources}")
    else:
        lines.append("- 待配置 OpenAI API 后生成。")

    technologies = [
        item
        for item in priority
        if item.noteworthy_technology not in {"", "待分析", "无特别技术"}
    ][:5]
    lines.extend(["", "## 特别值得注意的技术", ""])
    if technologies:
        for item in technologies:
            lines.extend(
                [
                    f"- **{item.noteworthy_technology}**（{item.full_name}）",
                    f"  - **改变了什么：** {item.technology_impact}",
                    f"  - **成熟度：** {item.maturity}",
                ]
            )
    else:
        lines.append("- 当前没有足够证据支持特别技术判断。")

    lines.extend(["", "## 产品与商业动态", ""])
    if analysis.product_business_signals:
        lines.extend(f"- {value}" for value in analysis.product_business_signals)
    else:
        lines.append("- 行业分析待生成，暂不推断商业化或竞争信号。")
    notable_risks = [
        item for item in priority if item.risks and item.risks != "待分析"
    ][:5]
    if analysis.available and notable_risks:
        lines.extend(["", "**需要保持警惕：**", ""])
        lines.extend(f"- **{item.full_name}：** {item.risks}" for item in notable_risks)

    lines.extend(["", "## 过去 7 天 / 30 天发生了什么变化", ""])
    lines.extend(_render_window("过去 7 天", trend_7d))
    lines.extend([""])
    lines.extend(_render_window("过去 30 天", trend_30d))

    lines.extend(["", "## 接下来值得关注", ""])
    if analysis.watch_next:
        lines.extend(f"- {value}" for value in analysis.watch_next)
    else:
        lines.append("- 等待更多有效日报后形成可验证的观察清单。")

    lines.extend(
        [
            "",
            "## 全榜附录",
            "",
            "| 项目 | 面向谁 | 解决什么问题 | AI 行业意义 | 关注度信号 |",
            "|---|---|---|---|---|",
        ]
    )
    insight_map = {item.full_name: item for item in analysis.repositories}
    for repo in repositories:
        insight = insight_map.get(repo.full_name)
        users = "、".join(insight.target_users) if insight else "待分析"
        problem = insight.problem_solved if insight else "待分析"
        relevance = insight.ai_relevance if insight else "待分析"
        signal = f"日榜第 {repo.rank}，当日新增 {repo.stars_today:,} Star"
        if repo.streak_days > 1:
            signal += f"，连续上榜 {repo.streak_days} 天"
        lines.append(
            f"| [{_escape_cell(repo.full_name)}]({repo.url}) | "
            f"{_escape_cell(users)} | {_escape_cell(problem)} | "
            f"{_escape_cell(relevance)} | {_escape_cell(signal)} |"
        )

    researched_count = sum(item.deep_researched for item in analysis.repositories)
    metadata_failures = sum(bool(repo.metadata_error) for repo in repositories)
    lines.extend(
        [
            "",
            "## 数据与判断边界",
            "",
            f"- 本次覆盖 {len(repositories)} 个 Trending 项目；"
            f"{researched_count} 个项目完成一手资料补充研究。",
            "- “首次出现”只指首次进入本报告历史，不代表项目或技术首次发布。",
            "- 项目方资料可能带有宣传倾向；商业化、成熟度和风险判断均需持续验证。",
            f"- 本次有 {metadata_failures} 个项目未完整取得 GitHub 补充资料。",
        ]
    )
    if analysis.error:
        lines.append(f"- 分析降级信息：{analysis.error}")
    return "\n".join(lines) + "\n"


def render_periodic_report(
    *,
    title: str,
    period_label: str,
    trend: Dict[str, object],
    snapshots: List[Dict[str, object]],
    minimum_days: int,
    synthesis: Optional[Dict[str, List[str]]] = None,
    synthesis_error: str = "",
) -> str:
    observed = int(trend["observed_days"])
    status = "完整复盘" if observed >= minimum_days else "观察期摘要"
    lines = [
        f"# {title} · {period_label}",
        "",
        f"> {status}；有效行业分析覆盖 {observed} 天。"
        "GitHub 热度只作为开发者关注信号。",
        "",
        "## 一句话结论",
        "",
    ]
    executive_summary = (synthesis or {}).get("executive_summary", [])
    if executive_summary:
        lines.extend(f"- {value}" for value in executive_summary)
    elif not observed:
        lines.append("- 尚无足够的行业分析数据，不能形成周期判断。")
    else:
        lines.append(
            f"- 本期持续受到关注的方向是 {_trend_names(trend['persistent'])}；"
            f"新出现方向是 {_trend_names(trend['emerging'])}。"
        )
    lines.extend(
        [
            "",
            "## 方向变化",
            "",
            f"- **正在增强：** {_trend_names(trend['accelerating'])}。",
            f"- **持续关注：** {_trend_names(trend['persistent'])}。",
            f"- **可能降温：** {_trend_names(trend['cooling'])}。",
            "",
            "## 用户需求变化",
            "",
        ]
    )
    if synthesis:
        sections = [
            ("用户需求变化", "customer_changes"),
            ("产品机会", "product_opportunities"),
            ("竞争格局变化", "competition_changes"),
            ("商业化信号", "commercial_signals"),
            ("主要风险", "risks"),
        ]
        for section_title, key in sections:
            lines.extend(["", f"## {section_title}", ""])
            values = synthesis.get(key, [])
            lines.extend(f"- {value}" for value in values)
            if not values:
                lines.append("- 尚无可靠结论。")
        lines.extend(["", "## 下一周期观察清单", ""])
        watch_next = synthesis.get("watch_next", [])
        lines.extend(f"- {value}" for value in watch_next)
        if not watch_next:
            lines.append("- 继续积累有效日报。")
        lines.extend(
            [
                "",
                "## 判断边界",
                "",
                f"- 本报告要求至少 {minimum_days} 个有效日报才能称为完整复盘；"
                f"当前覆盖 {observed} 天。",
                "- 频次上升表示开发者注意力增强，不自动代表市场需求或商业成功。",
            ]
        )
        return "\n".join(lines) + "\n"
    top_users = trend.get("top_users", [])
    if top_users:
        lines.extend(
            f"- {item['name']}：在 {item['count']} 个项目判断中出现"
            for item in top_users[:6]
        )
    else:
        lines.append("- 尚无足够数据。")
    lines.extend(["", "## 产品形态与商业信号", ""])
    forms = trend.get("top_product_forms", [])
    if forms:
        lines.extend(
            f"- {item['name']}：出现 {item['count']} 次" for item in forms[:6]
        )
    else:
        lines.append("- 尚无足够数据。")

    judgments: List[str] = []
    watch_items: List[str] = []
    for snapshot in snapshots:
        analysis = snapshot.get("industry_analysis", {})
        judgments.extend(str(v) for v in analysis.get("key_judgments", []))
        watch_items.extend(str(v) for v in analysis.get("watch_next", []))
    lines.extend(["", "## 本期重要判断", ""])
    if judgments:
        lines.extend(f"- {value}" for value in judgments[-8:])
    else:
        lines.append("- 尚无足够数据。")
    lines.extend(["", "## 下一周期观察清单", ""])
    if watch_items:
        lines.extend(f"- {value}" for value in watch_items[-8:])
    else:
        lines.append("- 继续积累有效日报。")
    lines.extend(
        [
            "",
            "## 判断边界",
            "",
            f"- 本报告要求至少 {minimum_days} 个有效日报才能称为完整复盘；"
            f"当前覆盖 {observed} 天。",
            "- 频次上升表示开发者注意力增强，不自动代表市场需求或商业成功。",
        ]
    )
    if synthesis_error:
        lines.append(f"- 分析降级信息：{synthesis_error}。")
    return "\n".join(lines) + "\n"


def render_reports_index(
    daily_files: List[Path],
    weekly_files: List[Path],
    monthly_files: List[Path],
) -> str:
    def links(files: List[Path], prefix: str = "") -> List[str]:
        return [
            f"- [{path.stem}]({prefix}{path.name})"
            for path in sorted(files, reverse=True)
        ]

    lines = ["# 历史行业情报", "", "## 日报", ""]
    lines.extend(links(daily_files) or ["- 尚无日报。"])
    lines.extend(["", "## 周报", ""])
    lines.extend(links(weekly_files, "weekly/") or ["- 尚无周报。"])
    lines.extend(["", "## 月报", ""])
    lines.extend(links(monthly_files, "monthly/") or ["- 尚无月报。"])
    return "\n".join(lines) + "\n"


def update_readme(
    content: str,
    latest_daily: date,
    latest_weekly: str = "",
    latest_monthly: str = "",
) -> str:
    marker_start = "<!-- latest-report:start -->"
    marker_end = "<!-- latest-report:end -->"
    items = [
        f"最新日报：[{latest_daily.isoformat()}]"
        f"(reports/{latest_daily.isoformat()}.md)"
    ]
    if latest_weekly:
        items.append(
            f"最新周报：[{latest_weekly}](reports/weekly/{latest_weekly}.md)"
        )
    if latest_monthly:
        items.append(
            f"最新月报：[{latest_monthly}](reports/monthly/{latest_monthly}.md)"
        )
    block = (
        f"{marker_start}\n"
        + " · ".join(items)
        + " · [查看全部历史](reports/index.md)\n"
        + f"{marker_end}"
    )
    if marker_start in content and marker_end in content:
        before, rest = content.split(marker_start, 1)
        _, after = rest.split(marker_end, 1)
        return before + block + after
    return content.rstrip() + "\n\n" + block + "\n"
