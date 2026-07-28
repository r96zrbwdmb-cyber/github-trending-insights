# GitHub Trending AI 行业情报

每天北京时间 09:00 自动观察 GitHub Trending 全榜，并生成面向 AI 行业从业者的中文简报。
它不讲编程语言或代码实现，而是回答：

- 今天哪些研究、产品和市场方向受到开发者关注？
- 项目面向谁，在解决什么问题？
- 哪些技术变化值得注意，会影响谁？
- 对产品机会、竞争、商业化和风险意味着什么？
- 相比过去 7 天和 30 天，哪些方向正在出现、增强、持续或降温？

<!-- latest-report:start -->
最新日报：[2026-07-28](reports/2026-07-28.md) · [查看全部历史](reports/index.md)
<!-- latest-report:end -->

## 报告体系

- `reports/YYYY-MM-DD.md`：约 5 分钟阅读的每日行业情报。
- `reports/weekly/YYYY-Www.md`：每周一生成的周度复盘。
- `reports/monthly/YYYY-MM.md`：每月 1 日生成的上月复盘。
- `data/YYYY-MM-DD.json`：可供滚动趋势计算的结构化快照。

GitHub 热度只被当作开发者关注度信号，不等同于市场采用、收入、融资或研究突破。

## 分析方式

1. 使用仓库简介、README 和历史表现分析全榜项目，统一回答目标用户、问题、产品方案、
   AI 行业意义、商业信号、成熟度和风险。
2. 选出最值得关注的 5–8 个项目，检索官网、论文或项目方正式资料，补充一手证据。
3. 从带版本的行业分类中计算滚动 7 天和 30 天变化，而不是统计编程语言或代码标签。

默认使用 `gpt-5.6-terra` 完成全榜分类，使用 `gpt-5.6-sol` 完成重点项目研究。

## 自动运行

GitHub Actions 每天 UTC 01:00（北京时间 09:00）运行。需要在仓库
**Settings → Secrets and variables → Actions** 中配置 `OPENAI_API_KEY`。

没有 API Key 时仍会采集和保存榜单，但报告会明确显示“行业分析待生成”，不会用技术标签
冒充行业洞察。

## 命令

```bash
# 每日采集和行业分析
python -m trending_report run

# 只采集数据
python -m trending_report run --no-ai

# 补生成周期报告
python -m trending_report weekly --end-date 2026-08-02
python -m trending_report monthly --month 2026-07

# 升级最近 30 天的旧快照
python -m trending_report reanalyze --days 30
```

环境变量：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `OPENAI_API_KEY` | 无 | OpenAI API 密钥 |
| `OPENAI_MODEL` | `gpt-5.6-terra` | 全榜行业分类模型 |
| `OPENAI_RESEARCH_MODEL` | `gpt-5.6-sol` | 一手资料研究模型 |
| `GITHUB_TOKEN` | 无 | GitHub API 令牌；Actions 自动提供 |
| `REPORT_TIMEZONE` | `Asia/Shanghai` | 日报日期使用的时区 |

## 验证

```bash
python -m unittest discover -s tests -v
python -m ruff check .
```

