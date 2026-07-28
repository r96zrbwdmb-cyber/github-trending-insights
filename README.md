# GitHub Trending 每日技术洞察

每天北京时间 09:00 自动抓取 GitHub Trending 全语言日榜 Top 25，用公开仓库元数据、
README 摘要和历史排名信号生成中文技术趋势报告。

报告重点回答：

- 今天开发者在关注什么？
- 哪些项目首次出现或排名快速上升？
- 涉及哪些技术、应用领域和实际用途？
- 哪些是可能的新技术，哪些只是已有技术再次升温？

<!-- latest-report:start -->
最新日报：[2026-07-28](reports/2026-07-28.md) · [查看全部历史](reports/index.md)
<!-- latest-report:end -->

## 快速开始

要求 Python 3.9 或更高版本，程序运行时不依赖第三方 Python 包。

```bash
python -m trending_report run --no-ai
```

启用 AI 分析：

```bash
export OPENAI_API_KEY="..."
python -m trending_report run
```

补跑指定日期：

```bash
python -m trending_report run --date 2026-07-28
```

可用环境变量：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `OPENAI_API_KEY` | 无 | OpenAI API 密钥；缺失时自动生成规则分析日报 |
| `OPENAI_MODEL` | `gpt-5.6-terra` | Responses API 模型 |
| `GITHUB_TOKEN` | 无 | GitHub API 令牌；Actions 会自动提供 |
| `REPORT_TIMEZONE` | `Asia/Shanghai` | 未指定 `--date` 时使用的时区 |

## GitHub Actions 配置

1. 在 GitHub 创建仓库，并将本项目推送到默认分支。
2. 在仓库的 **Settings → Secrets and variables → Actions** 中新增
   `OPENAI_API_KEY`。
3. 在 **Actions** 页面手动运行一次 **Daily GitHub Trending Insights**。

工作流也会每天 UTC 01:00（北京时间 09:00）运行。GitHub 的定时任务可能有少量排队延迟。
只有程序成功生成有效日报时，工作流才会提交 `data/`、`reports/` 和 README 的变化。

## 数据说明

- `data/YYYY-MM-DD.json`：每日结构化快照、规则分析和 AI 结果。
- `data/index.json`：首次/最近出现时间、最新排名和连续上榜天数。
- `reports/YYYY-MM-DD.md`：中文日报。
- `reports/index.md`：历史日报索引。

Trending 是短期关注度信号，不等同于技术质量、生产成熟度或长期采用率。程序不会执行所分析
仓库中的代码，也不会把 API 密钥或完整响应头写入报告。

## 开发与验证

```bash
python -m unittest discover -s tests -v
python -m ruff check .
```

