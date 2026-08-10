from __future__ import annotations

import calendar
import json
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from .analysis import (
    apply_history,
    build_index,
    load_snapshots,
    summarize_day_over_day,
    summarize_window,
    valid_industry_snapshots,
)
from .clients import GitHubClient, OpenAIClient
from .fallback import build_fallback_analysis
from .models import IndustryAnalysis, Repository
from .producthunt import (
    OfficialSiteReader,
    Product,
    ProductHuntClient,
    SourcePage,
    analyze_products,
    latest_complete_day,
    product_analysis_quality_errors,
    producthunt_token,
    render_product_report,
    summarize_product_history,
)
from .quality import github_analysis_quality_errors
from .report import (
    render_daily_report,
    render_periodic_report,
    render_reports_index,
    update_readme,
)
from .site import build_site


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _openai_client() -> OpenAIClient:
    provider = os.environ.get("AI_PROVIDER", "github").lower()
    api_key = (
        os.environ.get("GITHUB_TOKEN", "")
        if provider == "github"
        else os.environ.get("OPENAI_API_KEY", "")
    )
    return OpenAIClient(
        api_key=api_key,
        model=os.environ.get(
            "AI_MODEL",
            "openai/gpt-4.1-mini" if provider == "github" else "gpt-5.6-terra",
        ),
        research_model=os.environ.get(
            "AI_RESEARCH_MODEL",
            "openai/gpt-4.1-mini" if provider == "github" else "gpt-5.6-sol",
        ),
        provider=provider,
    )


def _synthesize_period(
    client: OpenAIClient,
    label: str,
    trend: Dict[str, Any],
    snapshots: List[Dict[str, Any]],
) -> tuple[Optional[Dict[str, List[str]]], str]:
    try:
        return client.synthesize_period(label, trend, snapshots), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: 周期 AI 综合不可用"


def _refresh_navigation(root: Path) -> None:
    reports_dir = root / "reports"
    daily_files = list(reports_dir.glob("????-??-??.md"))
    weekly_files = list((reports_dir / "weekly").glob("????-W??.md"))
    monthly_files = list((reports_dir / "monthly").glob("????-??.md"))
    atomic_write(
        reports_dir / "index.md",
        render_reports_index(daily_files, weekly_files, monthly_files),
    )
    if not daily_files:
        return
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    latest_daily = max(date.fromisoformat(path.stem) for path in daily_files)
    latest_weekly = max((path.stem for path in weekly_files), default="")
    latest_monthly = max((path.stem for path in monthly_files), default="")
    atomic_write(
        readme_path,
        update_readme(readme, latest_daily, latest_weekly, latest_monthly),
    )


def run(
    root: Path,
    report_date: date,
    *,
    no_ai: bool = False,
    github: Optional[GitHubClient] = None,
    openai: Optional[OpenAIClient] = None,
    minimum_repositories: int = 10,
) -> Path:
    github = github or GitHubClient(token=os.environ.get("GITHUB_TOKEN", ""))
    repositories = github.fetch_trending(limit=25)
    if len(repositories) < minimum_repositories:
        raise RuntimeError(
            f"仅解析到 {len(repositories)} 个仓库"
            f"（最低要求 {minimum_repositories}），"
            "为避免覆盖有效日报，本次停止写入"
        )
    for repository in repositories:
        github.enrich(repository)

    data_dir = root / "data"
    reports_dir = root / "reports"
    prior_snapshots = load_snapshots(data_dir, before=report_date)
    apply_history(repositories, prior_snapshots, report_date)
    if no_ai:
        industry_analysis = IndustryAnalysis.unavailable(
            repositories,
            "通过 --no-ai 禁用了 AI，行业分析待生成",
        )
    else:
        industry_analysis = (openai or _openai_client()).analyze(repositories)
        quality_errors = github_analysis_quality_errors(
            industry_analysis, len(repositories)
        )
        if quality_errors:
            industry_analysis = build_fallback_analysis(
                repositories,
                "模型输出质量检查未通过：" + "、".join(quality_errors),
            )
            fallback_errors = github_analysis_quality_errors(
                industry_analysis, len(repositories)
            )
            if fallback_errors:
                raise RuntimeError(
                    "GitHub 行业分析质量检查未通过："
                    + "、".join(fallback_errors)
                )

    snapshot = {
        "date": report_date.isoformat(),
        "source": "https://github.com/trending?since=daily",
        "repository_count": len(repositories),
        "repositories": [repo.to_dict() for repo in repositories],
        "industry_analysis": industry_analysis.to_dict(),
    }
    all_snapshots = [
        *prior_snapshots,
        snapshot,
        *[
            item
            for item in load_snapshots(data_dir, before=date.max)
            if item.get("date", "") > report_date.isoformat()
        ],
    ]
    trend_7d = summarize_window(all_snapshots, report_date, 7)
    trend_30d = summarize_window(all_snapshots, report_date, 30)
    day_over_day = summarize_day_over_day(
        repositories, prior_snapshots, report_date
    )
    report_content = render_daily_report(
        report_date,
        repositories,
        industry_analysis,
        trend_7d,
        trend_30d,
        day_over_day,
    )
    index_path = data_dir / "index.json"
    index = build_index(repositories, _load_json(index_path), report_date)

    data_path = data_dir / f"{report_date.isoformat()}.json"
    report_path = reports_dir / f"{report_date.isoformat()}.md"
    atomic_write(data_path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    atomic_write(index_path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    atomic_write(report_path, report_content)

    if report_date.weekday() == 0:
        generate_weekly(root, report_date - timedelta(days=1), openai=openai)
    if report_date.day == 1:
        previous_month_end = report_date - timedelta(days=1)
        generate_monthly(
            root,
            f"{previous_month_end.year:04d}-{previous_month_end.month:02d}",
            openai=openai,
        )
    _refresh_navigation(root)
    return report_path


def run_producthunt(
    root: Path,
    report_date: Optional[date] = None,
    *,
    producthunt: Optional[ProductHuntClient] = None,
    reader: Optional[OfficialSiteReader] = None,
    openai: Optional[OpenAIClient] = None,
    minimum_products: int = 10,
) -> Path:
    report_date = report_date or latest_complete_day()
    client = producthunt or ProductHuntClient(producthunt_token())
    products = client.fetch_daily(report_date, limit=15)
    if len(products) < minimum_products:
        raise RuntimeError(
            f"仅获取到 {len(products)} 个 Product Hunt 产品"
            f"（最低要求 {minimum_products}），为避免覆盖有效结果，本次停止写入"
        )
    site_reader = reader or OfficialSiteReader()
    for product in products:
        site_reader.enrich(product)
    analysis = analyze_products(products, openai or _openai_client())
    quality_errors = product_analysis_quality_errors(analysis, len(products))
    if quality_errors or not analysis.get("available"):
        raise RuntimeError(
            "Product Hunt 商业分析质量检查未通过："
            + "、".join(quality_errors or [str(analysis.get("error", "未知错误"))])
        )
    data_dir = root / "data" / "producthunt"
    snapshot: Dict[str, Any] = {
        "date": report_date.isoformat(),
        "timezone": "America/Los_Angeles",
        "source": "https://api.producthunt.com/v2/api/graphql",
        "product_count": len(products),
        "products": [item.to_dict() for item in products],
        "analysis": analysis,
    }
    # Include the current snapshot when calculating rolling coverage without
    # writing it first, so a failed analysis can never replace prior data.
    existing = data_dir / f"{report_date.isoformat()}.json"
    previous = existing.read_text(encoding="utf-8") if existing.exists() else None
    atomic_write(existing, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    try:
        snapshot["trend_7d"] = summarize_product_history(data_dir, report_date, 7)
        snapshot["trend_30d"] = summarize_product_history(data_dir, report_date, 30)
        atomic_write(existing, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        report_path = root / "reports" / "producthunt" / f"{report_date}.md"
        atomic_write(report_path, render_product_report(snapshot))
    except Exception:
        if previous is None:
            existing.unlink(missing_ok=True)
        else:
            atomic_write(existing, previous)
        raise
    return report_path


def run_all(
    root: Path,
    report_date: Optional[date] = None,
    *,
    no_ai: bool = False,
) -> List[Path]:
    outputs: List[Path] = []
    github_date = report_date or datetime.now(
        ZoneInfo(os.environ.get("REPORT_TIMEZONE", "Asia/Shanghai"))
    ).date()
    outputs.append(run(root, github_date, no_ai=no_ai))
    outputs.append(run_producthunt(root, report_date))
    outputs.append(build_site(root))
    return outputs


def generate_weekly(
    root: Path,
    end_date: date,
    *,
    openai: Optional[OpenAIClient] = None,
) -> Path:
    snapshots = load_snapshots(root / "data", before=end_date, include_current=True)
    trend = summarize_window(snapshots, end_date, 7)
    selected = valid_industry_snapshots(snapshots, end_date, 7)
    iso_year, iso_week, _ = end_date.isocalendar()
    label = f"{iso_year:04d}-W{iso_week:02d}"
    synthesis, synthesis_error = _synthesize_period(
        openai or _openai_client(), label, trend, selected
    )
    report = render_periodic_report(
        title="AI 行业周度复盘",
        period_label=label,
        trend=trend,
        snapshots=selected,
        minimum_days=5,
        synthesis=synthesis,
        synthesis_error=synthesis_error,
    )
    path = root / "reports" / "weekly" / f"{label}.md"
    atomic_write(path, report)
    _refresh_navigation(root)
    return path


def generate_monthly(
    root: Path,
    month: str,
    *,
    openai: Optional[OpenAIClient] = None,
) -> Path:
    try:
        year_text, month_text = month.split("-", 1)
        year, month_number = int(year_text), int(month_text)
        end_date = date(year, month_number, calendar.monthrange(year, month_number)[1])
    except (ValueError, IndexError) as exc:
        raise ValueError("月份必须采用 YYYY-MM 格式") from exc
    snapshots = load_snapshots(root / "data", before=end_date, include_current=True)
    window_days = calendar.monthrange(year, month_number)[1]
    trend = summarize_window(snapshots, end_date, window_days)
    selected = valid_industry_snapshots(snapshots, end_date, window_days)
    synthesis, synthesis_error = _synthesize_period(
        openai or _openai_client(), month, trend, selected
    )
    report = render_periodic_report(
        title="AI 行业月度复盘",
        period_label=month,
        trend=trend,
        snapshots=selected,
        minimum_days=20,
        synthesis=synthesis,
        synthesis_error=synthesis_error,
    )
    path = root / "reports" / "monthly" / f"{month}.md"
    atomic_write(path, report)
    _refresh_navigation(root)
    return path


def reanalyze(
    root: Path,
    days: int,
    *,
    openai: Optional[OpenAIClient] = None,
    fallback: bool = False,
) -> List[Path]:
    client = openai or _openai_client()
    if not fallback and not client.api_key:
        raise RuntimeError("reanalyze 需要可用的 GitHub Models 或 OpenAI 凭证")
    data_dir = root / "data"
    paths = sorted(data_dir.glob("????-??-??.json"))[-days:]
    updated: List[Path] = []
    for path in paths:
        snapshot = _load_json(path)
        if not snapshot.get("repositories"):
            continue
        repositories = [
            Repository.from_dict(item) for item in snapshot["repositories"]
        ]
        analysis = (
            build_fallback_analysis(
                repositories,
                "手动选择基于 GitHub 项目资料的免费规则分析",
            )
            if fallback
            else client.analyze(repositories)
        )
        quality_errors = github_analysis_quality_errors(analysis, len(repositories))
        if quality_errors:
            analysis = build_fallback_analysis(
                repositories, "历史重建时质量检查触发规则分析：" + "、".join(quality_errors)
            )
        final_errors = github_analysis_quality_errors(analysis, len(repositories))
        if final_errors:
            raise RuntimeError(
                f"{snapshot['date']} GitHub 历史分析质量不合格："
                + "、".join(final_errors)
            )
        snapshot["industry_analysis"] = analysis.to_dict()
        snapshot.pop("ai_analysis", None)
        snapshot.pop("rule_analysis", None)
        report_date = date.fromisoformat(snapshot["date"])
        all_snapshots = load_snapshots(data_dir, before=date.max)
        all_snapshots = [
            snapshot if item.get("date") == snapshot["date"] else item
            for item in all_snapshots
        ]
        atomic_write(path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        report_path = root / "reports" / f"{report_date.isoformat()}.md"
        atomic_write(
            report_path,
            render_daily_report(
                report_date,
                repositories,
                analysis,
                summarize_window(all_snapshots, report_date, 7),
                summarize_window(all_snapshots, report_date, 30),
                summarize_day_over_day(
                    repositories,
                    [
                        item
                        for item in all_snapshots
                        if item.get("date", "") < snapshot["date"]
                    ],
                    report_date,
                ),
            ),
        )
        updated.append(report_path)
    product_dir = data_dir / "producthunt"
    product_paths = sorted(product_dir.glob("????-??-??.json"))[-days:]
    for path in product_paths:
        snapshot = _load_json(path)
        products: List[Product] = []
        for value in snapshot.get("products", []):
            fields = {
                key: value.get(key)
                for key in Product.__dataclass_fields__
                if key != "source_pages"
            }
            fields["source_pages"] = [
                SourcePage(
                    url=str(page.get("url", "")),
                    title=str(page.get("title", "")),
                    excerpt=str(page.get("excerpt", "")),
                    kind=str(page.get("kind", "官网")),
                )
                for page in value.get("source_pages", [])
            ]
            products.append(Product(**fields))
        if not products:
            continue
        product_analysis = analyze_products(
            products, None if fallback else client
        )
        product_errors = product_analysis_quality_errors(
            product_analysis, len(products)
        )
        if product_errors or not product_analysis.get("available"):
            # analyze_products(None) is the deterministic, evidence-based fallback.
            product_analysis = analyze_products(products, None)
            product_errors = product_analysis_quality_errors(
                product_analysis, len(products)
            )
        if product_errors or not product_analysis.get("available"):
            raise RuntimeError(
                f"{snapshot.get('date')} Product Hunt 历史分析质量不合格："
                + "、".join(product_errors or [str(product_analysis.get("error", ""))])
            )
        snapshot["analysis"] = product_analysis
        atomic_write(path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")

    # Recalculate Product Hunt rolling windows only after every selected day has
    # been upgraded, so old template labels cannot leak into newer summaries.
    for path in product_paths:
        snapshot = _load_json(path)
        if not snapshot.get("products"):
            continue
        report_date = date.fromisoformat(snapshot["date"])
        snapshot["trend_7d"] = summarize_product_history(
            product_dir, report_date, 7
        )
        snapshot["trend_30d"] = summarize_product_history(
            product_dir, report_date, 30
        )
        atomic_write(path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
        report_path = root / "reports" / "producthunt" / f"{report_date}.md"
        atomic_write(report_path, render_product_report(snapshot))
        updated.append(report_path)
    _refresh_navigation(root)
    build_site(root)
    return updated
