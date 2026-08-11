# GitHub Trending AI 行业情报

**统一网页：<https://r96zrbwdmb-cyber.github.io/github-trending-insights/>**

网页顶部可在 GitHub Trending 与 Product Hunt 每日商业情报之间切换。

每天北京时间 09:00 自动观察 GitHub Trending 全榜，并生成面向 AI 行业从业者的中文简报。
它不讲编程语言或代码实现，而是回答：

- 今天哪些研究、产品和市场方向受到开发者关注？
- 项目面向谁，在解决什么问题？
- 哪些技术变化值得注意，会影响谁？
- 对产品机会、竞争、商业化和风险意味着什么？
- 相比过去 7 天和 30 天，哪些方向正在出现、增强、持续或降温？

<!-- latest-report:start -->
最新日报：[2026-08-11](reports/2026-08-11.md) · 最新周报：[2026-W32](reports/weekly/2026-W32.md) · 最新月报：[2026-07](reports/monthly/2026-07.md) · [查看全部历史](reports/index.md)
<!-- latest-report:end -->

## 报告体系

- `reports/YYYY-MM-DD.md`：约 15 分钟阅读的深度行业情报。
- `reports/producthunt/YYYY-MM-DD.md`：Product Hunt Top 15 商业解读。
- `reports/weekly/YYYY-Www.md`：每周一生成的周度复盘。
- `reports/monthly/YYYY-MM.md`：每月 1 日生成的上月复盘。
- `data/YYYY-MM-DD.json`：可供滚动趋势计算的结构化快照。

GitHub 热度只被当作开发者关注度信号，不等同于市场采用、收入、融资或研究突破。

## 分析方式

1. 使用仓库简介、README 和历史表现分析全榜项目，统一回答目标用户、问题、产品方案、
   AI 行业意义、商业信号、成熟度和风险。
2. 免费模式使用仓库页面、README 和项目历史作为一手资料，不执行收费网页检索。
3. 从带版本的行业分类中计算滚动 7 天和 30 天变化，而不是统计编程语言或代码标签。

默认通过 GitHub Models 免费额度调用 `openai/gpt-4.1-mini`。为满足免费额度的
单次 Token 限制，全榜会逐项目分析并核对是否漏项。重点项目同时提供通俗解释、
使用场景、直接好处、行业影响和验证信号。免费额度耗尽时分析自动停止，
不会自动转为付费。

每份日报同时启用“可校对模式”：

- `已验证事实`：来自结构化 GitHub 数据。
- `项目方说法`：程序已在 README 找到模型引用的对应原文。
- `分析判断`：行业推断，不作为事实引用。
- `证据不足`：原文匹配失败或缺少来源，进入人工核实清单。

README 原文匹配只能证明项目方确实做出该表述，不代表能力已经被独立验证。

## 自动运行

GitHub Actions 每天 UTC 01:17（北京时间 09:17）运行，以避开整点调度拥堵。
工作流使用 GitHub 自动提供的
`GITHUB_TOKEN` 和 GitHub Models 免费额度，不需要配置第三方 API Key。

公开仓库使用标准 GitHub 托管运行器不收取 Actions 分钟费用。

Product Hunt 使用官方 API，每天北京时间约 17:15 生成上一完整太平洋日榜单。
需要一次性在仓库 Actions Secret 中配置 `PRODUCT_HUNT_TOKEN`。

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

# Product Hunt 与统一网页
python -m trending_report producthunt
python -m trending_report producthunt --date 2026-07-29
python -m trending_report build-site
python -m trending_report run-all
```

环境变量：

| 变量 | 默认值 | 用途 |
|---|---|---|
| `AI_PROVIDER` | `github` | `github` 使用免费 GitHub Models；也可设为 `openai` |
| `AI_MODEL` | `openai/gpt-4.1-mini` | 全榜行业分类模型 |
| `AI_RESEARCH_MODEL` | `openai/gpt-4.1-mini` | 周期综合模型 |
| `OPENAI_API_KEY` | 无 | 仅在主动改用 `openai` 提供商时需要 |
| `GITHUB_TOKEN` | 无 | GitHub API 令牌；Actions 自动提供 |
| `PRODUCT_HUNT_TOKEN` | 无 | Product Hunt 官方 Developer Token |
| `REPORT_TIMEZONE` | `Asia/Shanghai` | 日报日期使用的时区 |

## 验证

```bash
python -m unittest discover -s tests -v
python -m ruff check .
```
