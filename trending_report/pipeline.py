from __future__ import annotations

import json
import os
import tempfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

from .analysis import apply_history, build_index, load_snapshots, summarize_clusters
from .clients import GitHubClient, OpenAIClient
from .models import AIAnalysis
from .report import render_report, render_reports_index, update_readme


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
    snapshots = load_snapshots(data_dir, before=report_date)
    apply_history(repositories, snapshots, report_date)
    clusters = summarize_clusters(repositories)

    if no_ai:
        analysis = AIAnalysis.unavailable("通过 --no-ai 禁用了 AI 分析")
    else:
        openai = openai or OpenAIClient(
            api_key=os.environ.get("OPENAI_API_KEY", ""),
            model=os.environ.get("OPENAI_MODEL", "gpt-5.6-terra"),
        )
        analysis = openai.analyze(repositories)

    snapshot = {
        "date": report_date.isoformat(),
        "source": "https://github.com/trending?since=daily",
        "repository_count": len(repositories),
        "repositories": [repo.to_dict() for repo in repositories],
        "rule_analysis": {
            "clusters": [{"name": name, "count": count} for name, count in clusters],
            "new_repositories": [repo.full_name for repo in repositories if repo.is_new],
        },
        "ai_analysis": analysis.to_dict(),
    }
    report_content = render_report(report_date, repositories, analysis, clusters)
    index_path = data_dir / "index.json"
    index = build_index(repositories, _load_json(index_path), report_date)

    # No output is touched until collection, enrichment and rendering have all completed.
    data_path = data_dir / f"{report_date.isoformat()}.json"
    report_path = reports_dir / f"{report_date.isoformat()}.md"
    atomic_write(data_path, json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n")
    atomic_write(index_path, json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    atomic_write(report_path, report_content)
    report_files = list(reports_dir.glob("????-??-??.md"))
    atomic_write(reports_dir / "index.md", render_reports_index(report_files))

    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
    latest_date = max(date.fromisoformat(path.stem) for path in report_files)
    atomic_write(readme_path, update_readme(readme, latest_date))
    return report_path
