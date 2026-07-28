from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

from .models import ANALYSIS_VERSION, IndustryAnalysis, Repository


def load_snapshots(
    data_dir: Path,
    before: date,
    *,
    include_current: bool = False,
) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    if not data_dir.exists():
        return snapshots
    for path in sorted(data_dir.glob("????-??-??.json")):
        try:
            snapshot_date = date.fromisoformat(path.stem)
            allowed = snapshot_date <= before if include_current else snapshot_date < before
            if allowed:
                snapshots.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, json.JSONDecodeError, OSError):
            continue
    return snapshots


def apply_history(
    repositories: List[Repository],
    snapshots: List[Dict[str, Any]],
    report_date: date,
) -> None:
    prior_positions: Dict[str, int] = {}
    seen: set = set()
    if snapshots:
        latest = snapshots[-1]
        prior_positions = {
            str(item["full_name"]): int(item["rank"])
            for item in latest.get("repositories", [])
            if "full_name" in item and "rank" in item
        }
    for snapshot in snapshots:
        seen.update(
            str(item["full_name"])
            for item in snapshot.get("repositories", [])
            if "full_name" in item
        )

    dated_members: Dict[date, set] = {}
    for snapshot in snapshots:
        try:
            snapshot_date = date.fromisoformat(str(snapshot["date"]))
        except (KeyError, ValueError):
            continue
        dated_members[snapshot_date] = {
            str(item["full_name"]) for item in snapshot.get("repositories", [])
        }

    for repo in repositories:
        repo.is_new = repo.full_name not in seen
        repo.previous_rank = prior_positions.get(repo.full_name)
        if repo.previous_rank is not None:
            repo.rank_change = repo.previous_rank - repo.rank
        cursor = report_date - timedelta(days=1)
        while repo.full_name in dated_members.get(cursor, set()):
            repo.streak_days += 1
            cursor -= timedelta(days=1)


def valid_industry_snapshots(
    snapshots: List[Dict[str, Any]],
    end_date: date,
    days: int,
) -> List[Dict[str, Any]]:
    start_date = end_date - timedelta(days=days - 1)
    valid: List[Dict[str, Any]] = []
    for snapshot in snapshots:
        try:
            snapshot_date = date.fromisoformat(str(snapshot["date"]))
            analysis = snapshot["industry_analysis"]
        except (KeyError, ValueError, TypeError):
            continue
        if not start_date <= snapshot_date <= end_date:
            continue
        if (
            analysis.get("available")
            and int(analysis.get("analysis_version", 0)) >= ANALYSIS_VERSION
        ):
            valid.append(snapshot)
    return valid


def summarize_window(
    snapshots: List[Dict[str, Any]],
    end_date: date,
    days: int,
) -> Dict[str, Any]:
    valid = valid_industry_snapshots(snapshots, end_date, days)
    if not valid:
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

    dated_themes: Dict[date, Counter] = {}
    user_counter: Counter = Counter()
    form_counter: Counter = Counter()
    theme_projects: Dict[str, set] = defaultdict(set)
    first_seen: Dict[str, date] = {}
    for snapshot in valid:
        snapshot_date = date.fromisoformat(snapshot["date"])
        daily: Counter = Counter()
        for item in snapshot["industry_analysis"].get("repositories", []):
            theme = str(item.get("industry_direction", "")).strip()
            if theme and theme != "行业分析待生成":
                daily[theme] += 1
                theme_projects[theme].add(str(item.get("full_name", "")))
                first_seen[theme] = min(first_seen.get(theme, snapshot_date), snapshot_date)
            user_counter.update(str(v) for v in item.get("target_users", []) if v)
            product_form = str(item.get("product_form", "")).strip()
            if product_form and product_form != "待分析":
                form_counter[product_form] += 1
        dated_themes[snapshot_date] = daily

    ordered_dates = sorted(dated_themes)
    split = max(1, len(ordered_dates) // 2)
    older_dates = ordered_dates[:split]
    recent_dates = ordered_dates[split:] or ordered_dates[-1:]
    older: Counter = Counter()
    recent: Counter = Counter()
    total: Counter = Counter()
    for current_date, values in dated_themes.items():
        total.update(values)
        (recent if current_date in recent_dates else older).update(values)

    themes = set(total)
    recent_rate = {
        theme: recent[theme] / max(1, len(recent_dates)) for theme in themes
    }
    older_rate = {
        theme: older[theme] / max(1, len(older_dates)) for theme in themes
    }
    emerging = [
        theme
        for theme in themes
        if first_seen[theme] in recent_dates and recent[theme] >= 1
    ]
    accelerating = [
        theme
        for theme in themes
        if recent[theme] >= 2
        and recent_rate[theme] > max(older_rate[theme] * 1.5, older_rate[theme] + 0.25)
    ]
    cooling = [
        theme
        for theme in themes
        if older[theme] >= 2
        and older_rate[theme] > max(recent_rate[theme] * 1.5, recent_rate[theme] + 0.25)
    ]
    persistent = [
        theme
        for theme in themes
        if sum(theme in dated_themes[value] for value in ordered_dates)
        >= max(2, len(ordered_dates) // 2)
    ]

    def rank(values: List[str]) -> List[Dict[str, Any]]:
        return [
            {
                "theme": theme,
                "appearances": total[theme],
                "project_count": len(theme_projects[theme]),
            }
            for theme in sorted(
                set(values),
                key=lambda item: (total[item], len(theme_projects[item])),
                reverse=True,
            )[:8]
        ]

    minimum = 5 if days == 7 else 20
    return {
        "window_days": days,
        "observed_days": len(valid),
        "status": "complete" if len(valid) >= minimum else "insufficient",
        "emerging": rank(emerging),
        "accelerating": rank(accelerating),
        "cooling": rank(cooling),
        "persistent": rank(persistent),
        "top_users": [
            {"name": name, "count": count}
            for name, count in user_counter.most_common(8)
        ],
        "top_product_forms": [
            {"name": name, "count": count}
            for name, count in form_counter.most_common(8)
        ],
    }


def build_index(
    repositories: List[Repository],
    existing: Dict[str, Any],
    report_date: date,
) -> Dict[str, Any]:
    records = dict(existing.get("repositories", {}))
    for repo in repositories:
        current = dict(records.get(repo.full_name, {}))
        current.setdefault("first_seen", report_date.isoformat())
        if report_date.isoformat() >= current.get("last_seen", ""):
            current.update(
                {
                    "last_seen": report_date.isoformat(),
                    "latest_rank": repo.rank,
                    "streak_days": repo.streak_days,
                }
            )
        if report_date.isoformat() < current["first_seen"]:
            current["first_seen"] = report_date.isoformat()
        records[repo.full_name] = current
    previous_success = str(existing.get("last_successful_run", ""))
    return {
        "last_successful_run": max(previous_success, report_date.isoformat()),
        "analysis_version": ANALYSIS_VERSION,
        "repositories": dict(sorted(records.items())),
    }


def snapshot_analysis(snapshot: Dict[str, Any]) -> IndustryAnalysis:
    value = snapshot.get("industry_analysis")
    if not isinstance(value, dict):
        return IndustryAnalysis(
            key_judgments=[],
            hot_characteristics=[],
            product_business_signals=[],
            watch_next=[],
            repositories=[],
            available=False,
            error="旧版快照没有行业分析",
            analysis_version=0,
        )
    return IndustryAnalysis.from_dict(value)
