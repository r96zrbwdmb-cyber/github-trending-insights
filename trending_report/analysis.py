from __future__ import annotations

import json
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .models import Repository


def load_snapshots(data_dir: Path, before: date) -> List[Dict[str, Any]]:
    snapshots: List[Dict[str, Any]] = []
    if not data_dir.exists():
        return snapshots
    for path in sorted(data_dir.glob("????-??-??.json")):
        try:
            snapshot_date = date.fromisoformat(path.stem)
            if snapshot_date < before:
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
        streak = 1
        cursor = report_date - timedelta(days=1)
        while repo.full_name in dated_members.get(cursor, set()):
            streak += 1
            cursor -= timedelta(days=1)
        repo.streak_days = streak


def summarize_clusters(repositories: Iterable[Repository], limit: int = 8) -> List[Tuple[str, int]]:
    counter: Counter = Counter()
    for repo in repositories:
        if repo.language:
            counter[f"语言:{repo.language}"] += 1
        for topic in repo.topics:
            counter[f"主题:{topic}"] += 1
    return counter.most_common(limit)


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
        "repositories": dict(sorted(records.items())),
    }
