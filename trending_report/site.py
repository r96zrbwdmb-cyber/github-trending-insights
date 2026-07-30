from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


def _load(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _latest(directory: Path) -> Dict[str, Any]:
    paths = sorted(directory.glob("????-??-??.json"))
    return _load(paths[-1]) if paths else {}


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def build_site(root: Path) -> Path:
    site = root / "site"
    output = root / "_site"
    output.mkdir(parents=True, exist_ok=True)
    for name in ["styles.css", "app.js"]:
        shutil.copyfile(site / name, output / name)

    github_days = sorted(
        path.stem for path in (root / "data").glob("????-??-??.json")
    )
    product_days = sorted(
        path.stem
        for path in (root / "data" / "producthunt").glob("????-??-??.json")
    )
    github = _latest(root / "data")
    producthunt = _latest(root / "data" / "producthunt")
    data = {
        "github": github,
        "producthunt": producthunt,
        "dates": {"github": github_days, "producthunt": product_days},
    }
    template = (site / "index.html").read_text(encoding="utf-8")
    page = template.replace("__SITE_DATA__", _json_for_script(data))
    (output / "index.html").write_text(page, encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")

    data_output = output / "data"
    data_output.mkdir(exist_ok=True)
    for source, platform in [
        (root / "data", "github"),
        (root / "data" / "producthunt", "producthunt"),
    ]:
        destination = data_output / platform
        destination.mkdir(exist_ok=True)
        for path in source.glob("????-??-??.json"):
            shutil.copyfile(path, destination / path.name)
    return output


def github_view(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    analysis = snapshot.get("industry_analysis", {})
    insight_map = {
        item.get("full_name"): item for item in analysis.get("repositories", [])
    }
    cards: List[Dict[str, Any]] = []
    for repo in snapshot.get("repositories", []):
        insight = insight_map.get(repo.get("full_name"), {})
        cards.append(
            {
                "rank": repo.get("rank"),
                "name": repo.get("full_name"),
                "url": repo.get("url"),
                "summary": insight.get("one_line_summary") or repo.get("description"),
                "users": insight.get("target_users", []),
                "problem": insight.get("problem_solved", "待分析"),
                "scenario": insight.get("plain_language_explanation", "待分析"),
                "benefits": insight.get("practical_benefits", []),
                "importance": insight.get("industry_implications", "待分析"),
                "confidence": insight.get("confidence", "低"),
            }
        )
    return {
        "date": snapshot.get("date", ""),
        "judgments": analysis.get("key_judgments", []),
        "characteristics": analysis.get("hot_characteristics", []),
        "cards": cards,
        "status": analysis.get("error", ""),
    }


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)
