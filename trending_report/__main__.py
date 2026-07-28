from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .pipeline import run


def current_report_date(timezone_name: str) -> date:
    try:
        return datetime.now(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"未知时区：{timezone_name}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 GitHub Trending 中文技术洞察日报")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="抓取、分析并生成日报")
    run_parser.add_argument(
        "--date",
        help="日报日期（YYYY-MM-DD），默认使用配置时区的今天",
    )
    run_parser.add_argument(
        "--no-ai",
        action="store_true",
        help="禁用 OpenAI，仅生成规则分析",
    )
    run_parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: object = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report_date = (
            date.fromisoformat(args.date)
            if args.date
            else current_report_date(os.environ.get("REPORT_TIMEZONE", "Asia/Shanghai"))
        )
        report = run(args.root.resolve(), report_date, no_ai=args.no_ai)
    except (ValueError, RuntimeError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"日报已生成：{report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
