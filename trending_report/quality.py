from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any, Dict, List

from .models import IndustryAnalysis


def _duplicate_error(values: List[Any], label: str) -> str:
    normalized = [json.dumps(value, ensure_ascii=False, sort_keys=True) for value in values]
    if normalized and Counter(normalized).most_common(1)[0][1] > max(3, len(values) // 3):
        return f"{label}重复率过高"
    return ""


def github_analysis_quality_errors(
    analysis: IndustryAnalysis, expected: int
) -> List[str]:
    if not analysis.available:
        return ["行业分析不可用"]
    insights = analysis.repositories
    errors: List[str] = []
    if len(insights) != expected:
        errors.append("项目分析数量与榜单不一致")
    for values, label in [
        ([item.practical_benefits for item in insights], "实际好处"),
        ([item.plain_language_explanation for item in insights], "通俗解释"),
    ]:
        error = _duplicate_error(values, label)
        if error:
            errors.append(error)
    placeholders = ["相关行业从业者", "暂不判断行业影响", "公开资料不足"]
    if sum(
        any(word in json.dumps(item.to_dict(), ensure_ascii=False) for word in placeholders)
        for item in insights
    ) > max(3, expected // 3):
        errors.append("占位式分析过多")
    english_only = sum(
        bool(re.fullmatch(r"[\x00-\x7f\s\W]+", item.plain_language_explanation or ""))
        for item in insights
    )
    if english_only > max(2, expected // 4):
        errors.append("通俗解释未完成中文化")
    return errors


def snapshot_quality_errors(snapshot: Dict[str, Any]) -> List[str]:
    """Validate stored output before website publication or email delivery."""
    errors: List[str] = []
    if "industry_analysis" in snapshot:
        try:
            analysis = IndustryAnalysis.from_dict(snapshot["industry_analysis"])
            errors.extend(
                github_analysis_quality_errors(
                    analysis, int(snapshot.get("repository_count", 0))
                )
            )
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"GitHub 分析结构无效：{type(exc).__name__}")
    return errors
