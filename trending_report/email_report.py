from __future__ import annotations

import html
import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, List

from .models import IndustryAnalysis
from .producthunt import product_analysis_quality_errors
from .quality import github_analysis_quality_errors

PUBLIC_SITE = "https://r96zrbwdmb-cyber.github.io/github-trending-insights/"


def _latest_snapshot(folder: Path) -> Dict[str, Any]:
    paths = sorted(folder.glob("????-??-??.json"))
    if not paths:
        return {}
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def _items(values: List[Any], limit: int = 5) -> str:
    if not values:
        return "<li>今日暂无可用结论，请打开完整页面查看原始榜单。</li>"
    return "".join(f"<li>{html.escape(str(value))}</li>" for value in values[:limit])


def _closing_periods(
    root: Path, platform: str, snapshot_date: str
) -> List[Dict[str, Any]]:
    values: List[Dict[str, Any]] = []
    for period_type in ["weekly", "monthly"]:
        directory = root / "data" / "periods" / platform / period_type
        paths = sorted(directory.glob("*.json"))
        if not paths:
            continue
        try:
            value = json.loads(paths[-1].read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("end_date") == snapshot_date:
            values.append(value)
    return values


def _period_email(root: Path, github_date: str, product_date: str) -> str:
    blocks: List[str] = []
    for platform, platform_name, snapshot_date in [
        ("github", "GitHub 行业信号", github_date),
        ("producthunt", "Product Hunt 商业信号", product_date),
    ]:
        for value in _closing_periods(root, platform, snapshot_date):
            period_name = "本周总结" if value.get("period_type") == "weekly" else "本月总结"
            observed = int(value.get("observed_days", 0))
            expected = int(value.get("expected_days", 0))
            platform_label = html.escape(platform_name)
            display_label = html.escape(
                str(value.get("display_label", "周期总结"))
            )
            summary_items = _items(value.get("executive_summary", []), 3)
            strengthening = html.escape(
                "、".join(value.get("strengthening", [])[:5])
                or "尚未形成可靠信号"
            )
            watch_next = html.escape(
                "、".join(value.get("watch_next", [])[:3])
                or "继续验证趋势是否持续"
            )
            blocks.append(
                f"""<div style="background:#fff;border:1px solid #111;padding:24px;margin:18px 0">
                  <p style="font-size:12px;letter-spacing:1px;margin:0">
                    {platform_label} · {period_name}
                  </p>
                  <h2 style="margin:8px 0">{display_label}</h2>
                  <p style="color:#666">有效观察 {observed}/{expected} 天</p>
                  <ul style="padding-left:22px;line-height:1.8">
                    {summary_items}
                  </ul>
                  <p><strong>正在增强：</strong>{strengthening}</p>
                  <p><strong>下一步关注：</strong>{watch_next}</p>
                </div>"""
            )
    if not blocks:
        return ""
    return "<h2 style=\"margin-top:36px\">周期总结</h2>" + "".join(blocks)


def build_daily_email(root: Path) -> tuple[str, str]:
    github = _latest_snapshot(root / "data")
    producthunt = _latest_snapshot(root / "data" / "producthunt")
    github_analysis = github.get("industry_analysis", {})
    product_analysis = producthunt.get("analysis", {})
    github_date = str(github.get("date", ""))
    product_date = str(producthunt.get("date", ""))
    report_date = max(
        str(github.get("date", "")),
        str(producthunt.get("date", "")),
    )
    subject = f"AI 行业每日情报｜{report_date or '最新'}"
    body = f"""\
<!doctype html>
<html lang="zh-CN">
<body style="margin:0;background:#f5f5f3;color:#111;font-family:Arial,'PingFang SC',sans-serif">
  <div style="max-width:720px;margin:auto;padding:36px 20px">
    <p style="font-size:12px;letter-spacing:2px">AI INDUSTRY DAILY</p>
    <h1 style="font-size:30px;margin:8px 0">今天值得关注什么？</h1>
    <p style="color:#666">GitHub 技术信号 + Product Hunt 产品与商业信号</p>

    <div style="background:#fff;border:1px solid #111;padding:24px;margin:28px 0">
      <h2 style="margin-top:0">GitHub Trending</h2>
      <ol style="padding-left:22px;line-height:1.8">
        {_items(github_analysis.get("key_judgments", []))}
      </ol>
      <a href="{PUBLIC_SITE}#github" style="color:#111;font-weight:bold">查看完整技术情报 →</a>
    </div>

    <div style="background:#111;color:#fff;padding:24px;margin:28px 0">
      <h2 style="margin-top:0">Product Hunt</h2>
      <ol style="padding-left:22px;line-height:1.8">
        {_items(product_analysis.get("key_judgments", []))}
      </ol>
      <a href="{PUBLIC_SITE}#producthunt" style="color:#fff;font-weight:bold">查看 Top 15 产品 →</a>
    </div>

    {_period_email(root, github_date, product_date)}

    <p style="color:#666;font-size:13px;line-height:1.7">
      榜单热度代表关注信号，不等于收入、融资、留存或市场采用。
      本邮件由每日自动任务生成。
    </p>
  </div>
</body>
</html>
"""
    return subject, body


def send_daily_email(root: Path) -> None:
    username = os.environ.get("SMTP_USERNAME", "").strip()
    password = os.environ.get("SMTP_APP_PASSWORD", "").replace(" ", "").strip()
    recipient = os.environ.get("REPORT_EMAIL_TO", "").strip()
    if not username or not password or not recipient:
        raise RuntimeError(
            "未完整配置 SMTP_USERNAME、SMTP_APP_PASSWORD 和 REPORT_EMAIL_TO"
        )
    github = _latest_snapshot(root / "data")
    producthunt = _latest_snapshot(root / "data" / "producthunt")
    github_errors = github_analysis_quality_errors(
        IndustryAnalysis.from_dict(github.get("industry_analysis", {})),
        int(github.get("repository_count", 0)),
    )
    product_errors = product_analysis_quality_errors(
        producthunt.get("analysis", {}), int(producthunt.get("product_count", 0))
    )
    if not producthunt.get("analysis", {}).get("available"):
        product_errors.append("商业分析不可用")
    if github_errors or product_errors:
        raise RuntimeError(
            "日报质量检查未通过，邮件已停止发送："
            + "、".join(github_errors + product_errors)
        )
    subject, body = build_daily_email(root)
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = username
    message["To"] = recipient
    message.set_content("请使用支持 HTML 的邮件客户端查看每日行业情报。")
    message.add_alternative(body, subtype="html")
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context, timeout=30) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
