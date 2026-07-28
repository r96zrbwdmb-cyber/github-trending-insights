from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

from .models import AIAnalysis, RepoInsight, Repository


def _escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_report(
    report_date: date,
    repositories: List[Repository],
    analysis: AIAnalysis,
    clusters: List[Tuple[str, int]],
) -> str:
    insight_map: Dict[str, RepoInsight] = {
        insight.full_name: insight for insight in analysis.repositories
    }
    new_repos = [repo for repo in repositories if repo.is_new]
    rising = sorted(
        [repo for repo in repositories if repo.rank_change and repo.rank_change > 0],
        key=lambda repo: repo.rank_change or 0,
        reverse=True,
    )
    watching = sorted(
        repositories,
        key=lambda repo: (repo.streak_days, repo.stars_today, -repo.rank),
        reverse=True,
    )[:8]

    lines = [
        f"# GitHub Trending 每日技术洞察 · {report_date.isoformat()}",
        "",
        "> 数据范围：GitHub Trending 全语言日榜 Top 25。"
        "首次上榜仅指首次出现在本报告历史中，"
        "不代表项目或技术首次发布。",
        "",
        "## 今日摘要",
        "",
    ]
    if analysis.available:
        lines.extend(f"- {item}" for item in analysis.daily_insights)
    else:
        lines.append(f"- ⚠️ 本次仅提供规则分析：{analysis.error}")
        lines.append(
            f"- 共采集 {len(repositories)} 个仓库；"
            f"{len(new_repos)} 个首次出现在本报告；"
            f"{sum(repo.stars_today for repo in repositories):,} 个当日新增 Star。"
        )

    lines.extend(["", "## 新发现", ""])
    if not new_repos:
        lines.append("- 今天没有首次出现在本报告历史中的仓库。")
    for repo in new_repos:
        insight = insight_map.get(repo.full_name)
        detail = insight.technology_summary if insight else repo.description or "暂无简介"
        lines.append(f"- **[{repo.full_name}]({repo.url})**：{detail}")
        if insight:
            domains = "、".join(insight.application_domains) or "未分类"
            use_cases = "；".join(insight.primary_use_cases) or "暂无"
            lines.append(f"  - 应用领域：{domains}；主要用途：{use_cases}")
            lines.append(f"  - 新颖性判断：{insight.novelty_reason}")

    lines.extend(["", "## 上升最快项目", ""])
    if not rising:
        lines.append("- 暂无可与前一日报比较的排名上升项目。")
    for repo in rising[:10]:
        lines.append(
            f"- **[{repo.full_name}]({repo.url})**：上升 {repo.rank_change} 位，"
            f"当前第 {repo.rank}，今日 +{repo.stars_today:,} Star。"
        )

    lines.extend(["", "## 技术 / 领域聚类", ""])
    if clusters:
        lines.extend(f"- {name}：{count} 个项目" for name, count in clusters)
    else:
        lines.append("- 缺少足够的语言和 topic 元数据，暂不能形成聚类。")

    lines.extend(["", "## 值得持续观察", ""])
    for repo in watching:
        insight = insight_map.get(repo.full_name)
        lines.append(
            f"- **[{repo.full_name}]({repo.url})**：连续上榜 {repo.streak_days} 天，"
            f"今日 +{repo.stars_today:,} Star。"
        )
        if insight:
            lines.append(f"  - 采用信号：{insight.adoption_signal}；")
            lines.append(f"  - 风险或限制：{insight.risks_or_limits}")

    lines.extend(
        [
            "",
            "## Top 25 简表",
            "",
            "| 排名 | 仓库 | 语言 | 总 Star | 今日新增 | 排名变化 | 连续上榜 |",
            "|---:|---|---|---:|---:|---:|---:|",
        ]
    )
    for repo in repositories:
        change = "新收录" if repo.is_new else (
            "—" if repo.rank_change is None else f"{repo.rank_change:+d}"
        )
        lines.append(
            f"| {repo.rank} | [{_escape_cell(repo.full_name)}]({repo.url}) | "
            f"{_escape_cell(repo.language or '—')} | {repo.stars:,} | "
            f"+{repo.stars_today:,} | {change} | {repo.streak_days} 天 |"
        )

    metadata_failures = sum(bool(repo.metadata_error) for repo in repositories)
    lines.extend(
        [
            "",
            "## 数据与分析限制",
            "",
            "- GitHub Trending 是动态页面；榜单只表示短期关注度，"
            "不等同于技术质量或长期采用率。",
            "- “首次出现”以本仓库已保存的日报为基准；"
            "删除历史数据会改变这一判断。",
            "- AI 分析基于公开仓库简介、topics、README 摘要和榜单信号，"
            "不执行仓库代码。",
            f"- 本次有 {metadata_failures} 个仓库的 GitHub API "
            "补充元数据未完整获取。",
        ]
    )
    if not analysis.available:
        lines.append(
            "- 本次 OpenAI 分析不可用，语义判断与项目级用途说明已降级。"
        )
    return "\n".join(lines) + "\n"


def render_reports_index(report_files: List[Path]) -> str:
    dates = sorted((path.stem for path in report_files if path.stem != "index"), reverse=True)
    lines = ["# 历史日报", ""]
    lines.extend(f"- [{value}]({value}.md)" for value in dates)
    if not dates:
        lines.append("- 尚无日报。")
    return "\n".join(lines) + "\n"


def update_readme(content: str, latest_date: date) -> str:
    marker_start = "<!-- latest-report:start -->"
    marker_end = "<!-- latest-report:end -->"
    block = (
        f"{marker_start}\n"
        f"最新日报：[{latest_date.isoformat()}](reports/{latest_date.isoformat()}.md) · "
        "[查看全部历史](reports/index.md)\n"
        f"{marker_end}"
    )
    if marker_start in content and marker_end in content:
        before, rest = content.split(marker_start, 1)
        _, after = rest.split(marker_end, 1)
        return before + block + after
    return content.rstrip() + "\n\n" + block + "\n"
