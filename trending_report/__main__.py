from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .pipeline import (
    build_site,
    generate_monthly,
    generate_weekly,
    reanalyze,
    run,
    run_all,
    run_producthunt,
)


def current_report_date(timezone_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"未知时区：{timezone_name}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 GitHub Trending AI 行业情报")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="抓取并生成每日行业情报")
    run_parser.add_argument(
        "--date",
        help="报告日期（YYYY-MM-DD），默认使用配置时区的今天",
    )
    run_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="只采集数据，将行业分析标记为待生成",
    )

    weekly_parser = subparsers.add_parser("weekly", help="补生成周度复盘")
    weekly_parser.add_argument(
        "--end-date",
        required=True,
        help="统计周期结束日期（YYYY-MM-DD）",
    )

    monthly_parser = subparsers.add_parser("monthly", help="补生成月度复盘")
    monthly_parser.add_argument("--month", required=True, help="月份（YYYY-MM）")

    reanalyze_parser = subparsers.add_parser("reanalyze", help="升级旧快照的行业分析")
    reanalyze_parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="重新分析最近多少天，默认 30",
    )
    reanalyze_parser.add_argument(
        "--fallback",
        action="store_true",
        help="使用免费规则分析重建，不调用外部 AI 模型",
    )
    producthunt_parser = subparsers.add_parser(
        "producthunt", help="生成 Product Hunt 每日商业情报"
    )
    producthunt_parser.add_argument(
        "--date", help="Product Hunt 日期（YYYY-MM-DD），默认上一完整日"
    )
    subparsers.add_parser("build-site", help="构建 GitHub 与 Product Hunt 统一网页")
    run_all_parser = subparsers.add_parser(
        "run-all", help="运行全部采集、分析并构建网页"
    )
    run_all_parser.add_argument("--date", help="补跑日期（YYYY-MM-DD）")
    run_all_parser.add_argument("--no-ai", action="store_true")
    return parser


def main(argv: object = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "run":
            report_date = (
                date.fromisoformat(args.date)
                if args.date
                else current_report_date(
                    os.environ.get("REPORT_TIMEZONE", "Asia/Shanghai")
                )
            )
            output = run(root, report_date, no_ai=args.no_ai)
            print(f"日报已生成：{output}")
        elif args.command == "weekly":
            output = generate_weekly(root, date.fromisoformat(args.end_date))
            print(f"周报已生成：{output}")
        elif args.command == "monthly":
            output = generate_monthly(root, args.month)
            print(f"月报已生成：{output}")
        elif args.command == "reanalyze":
            if args.days < 1:
                raise ValueError("--days 必须大于 0")
            outputs = reanalyze(root, args.days, fallback=args.fallback)
            print(f"已重新分析 {len(outputs)} 份日报")
        elif args.command == "producthunt":
            output = run_producthunt(
                root, date.fromisoformat(args.date) if args.date else None
            )
            print(f"Product Hunt 日报已生成：{output}")
        elif args.command == "build-site":
            output = build_site(root)
            print(f"统一网页已生成：{output}")
        else:
            outputs = run_all(
                root,
                date.fromisoformat(args.date) if args.date else None,
                no_ai=args.no_ai,
            )
            print(f"全部内容已生成：{len(outputs)} 项")
    except (ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
