from __future__ import annotations

import calendar
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .analysis import summarize_window, valid_industry_snapshots
from .producthunt import summarize_product_history


def _load_snapshots(directory: Path) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    for path in sorted(directory.glob("????-??-??.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            date.fromisoformat(str(value.get("date", "")))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        snapshots.append(value)
    return snapshots


def _unique(values: Iterable[Any], limit: int = 6) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _theme_names(values: Iterable[Dict[str, Any]]) -> List[str]:
    return _unique(item.get("theme", "") for item in values)


def _pair_names(values: Iterable[Any]) -> List[str]:
    names: List[str] = []
    for item in values:
        if isinstance(item, (list, tuple)) and item:
            names.append(str(item[0]))
        elif isinstance(item, dict):
            names.append(str(item.get("name") or item.get("category") or ""))
    return _unique(names)


def _period_label(period_type: str, end_date: date) -> tuple[str, str, int, int]:
    if period_type == "weekly":
        iso_year, iso_week, _ = end_date.isocalendar()
        return (
            f"{iso_year:04d}-W{iso_week:02d}",
            f"{iso_year} 年第 {iso_week} 周",
            7,
            5,
        )
    days = calendar.monthrange(end_date.year, end_date.month)[1]
    return (
        f"{end_date.year:04d}-{end_date.month:02d}",
        f"{end_date.year} 年 {end_date.month} 月",
        days,
        20,
    )


def github_period_summary(
    snapshots: List[Dict[str, Any]],
    end_date: date,
    period_type: str,
    synthesis: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    label, display_label, window_days, minimum_days = _period_label(
        period_type, end_date
    )
    trend = summarize_window(snapshots, end_date, window_days)
    selected = valid_industry_snapshots(snapshots, end_date, window_days)
    emerging = _theme_names(trend.get("emerging", []))
    strengthening = _theme_names(trend.get("accelerating", []))
    persistent = _theme_names(trend.get("persistent", []))
    cooling = _theme_names(trend.get("cooling", []))
    executive = _unique((synthesis or {}).get("executive_summary", []), 4)
    if not executive:
        if persistent:
            executive.append(f"持续受到关注的方向是{'、'.join(persistent[:4])}。")
        if strengthening:
            executive.append(f"本期增强最明显的是{'、'.join(strengthening[:4])}。")
        if emerging:
            executive.append(f"新进入观察范围的是{'、'.join(emerging[:4])}。")
    judgments = _unique(
        value
        for snapshot in reversed(selected)
        for value in snapshot.get("industry_analysis", {}).get("key_judgments", [])
    )
    watch_next = _unique(
        [*(synthesis or {}).get("watch_next", [])]
        + [
            value
            for snapshot in reversed(selected)
            for value in snapshot.get("industry_analysis", {}).get("watch_next", [])
        ]
    )
    observed = int(trend.get("observed_days", 0))
    return {
        "platform": "github",
        "period_type": period_type,
        "label": label,
        "display_label": display_label,
        "end_date": end_date.isoformat(),
        "observed_days": observed,
        "expected_days": window_days,
        "status": "complete" if observed >= minimum_days else "observing",
        "executive_summary": executive or ["有效历史仍不足，暂不形成方向性结论。"],
        "emerging": emerging,
        "strengthening": strengthening,
        "persistent": persistent,
        "cooling": cooling,
        "audiences": _pair_names(trend.get("top_users", [])),
        "business_models": _pair_names(trend.get("top_product_forms", [])),
        "key_judgments": judgments,
        "watch_next": watch_next,
        "limits": "GitHub 热度代表开发者注意力，不等于市场采用或商业成功。",
    }


def producthunt_period_summary(
    data_dir: Path,
    snapshots: List[Dict[str, Any]],
    end_date: date,
    period_type: str,
) -> Dict[str, Any]:
    label, display_label, window_days, minimum_days = _period_label(
        period_type, end_date
    )
    trend = summarize_product_history(data_dir, end_date, window_days)
    start_ordinal = end_date.toordinal() - window_days + 1
    selected = [
        item
        for item in snapshots
        if start_ordinal
        <= date.fromisoformat(str(item.get("date"))).toordinal()
        <= end_date.toordinal()
    ]
    top_categories = _pair_names(trend.get("top_categories", []))
    strengthening = _pair_names(trend.get("strengthening", []))
    cooling = _pair_names(trend.get("cooling", []))
    pricing = _pair_names(trend.get("pricing_patterns", []))
    audiences = _pair_names(trend.get("customer_patterns", []))
    executive: List[str] = []
    if top_categories:
        executive.append(f"本期最常见的产品方向是{'、'.join(top_categories[:4])}。")
    if strengthening:
        executive.append(f"正在升温的产品类别是{'、'.join(strengthening[:4])}。")
    if pricing:
        executive.append(f"较常见的收费方式是{'、'.join(pricing[:3])}。")
    judgments = _unique(
        value
        for snapshot in reversed(selected)
        for value in snapshot.get("analysis", {}).get("key_judgments", [])
    )
    watch_next = _unique(
        value
        for snapshot in reversed(selected)
        for value in snapshot.get("analysis", {}).get("new_product_forms", [])
    )
    observed = int(trend.get("observed_days", 0))
    return {
        "platform": "producthunt",
        "period_type": period_type,
        "label": label,
        "display_label": display_label,
        "end_date": end_date.isoformat(),
        "observed_days": observed,
        "expected_days": window_days,
        "status": "complete" if observed >= minimum_days else "observing",
        "executive_summary": executive or ["有效历史仍不足，暂不形成产品方向结论。"],
        "emerging": [],
        "strengthening": strengthening,
        "persistent": top_categories,
        "cooling": cooling,
        "audiences": audiences,
        "business_models": pricing,
        "key_judgments": judgments,
        "watch_next": watch_next,
        "limits": "Product Hunt 热度代表社区关注，不等于收入、留存或商业成功。",
    }


def is_month_end(value: date) -> bool:
    return value.day == calendar.monthrange(value.year, value.month)[1]


def period_path(root: Path, platform: str, period_type: str, label: str) -> Path:
    return root / "data" / "periods" / platform / period_type / f"{label}.json"


def write_period_summary(root: Path, payload: Dict[str, Any]) -> Path:
    path = period_path(
        root,
        str(payload["platform"]),
        str(payload["period_type"]),
        str(payload["label"]),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def ensure_period_summaries(root: Path) -> None:
    """Backfill deterministic summaries for completed periods in existing history."""
    github_snapshots = _load_snapshots(root / "data")
    product_snapshots = _load_snapshots(root / "data" / "producthunt")
    for platform, snapshots in [
        ("github", github_snapshots),
        ("producthunt", product_snapshots),
    ]:
        for snapshot in snapshots:
            end_date = date.fromisoformat(str(snapshot["date"]))
            period_types = []
            if end_date.weekday() == 6:
                period_types.append("weekly")
            if is_month_end(end_date):
                period_types.append("monthly")
            for period_type in period_types:
                label = _period_label(period_type, end_date)[0]
                path = period_path(root, platform, period_type, label)
                if path.exists():
                    continue
                payload = (
                    github_period_summary(
                        github_snapshots, end_date, period_type
                    )
                    if platform == "github"
                    else producthunt_period_summary(
                        root / "data" / "producthunt",
                        product_snapshots,
                        end_date,
                        period_type,
                    )
                )
                write_period_summary(root, payload)


def load_periods(root: Path, platform: str) -> Dict[str, List[Dict[str, Any]]]:
    result: Dict[str, List[Dict[str, Any]]] = {"weekly": [], "monthly": []}
    for period_type in result:
        directory = root / "data" / "periods" / platform / period_type
        values: List[Dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                date.fromisoformat(str(value.get("end_date", "")))
            except (OSError, ValueError, json.JSONDecodeError):
                continue
            values.append(value)
        result[period_type] = values
    return result
