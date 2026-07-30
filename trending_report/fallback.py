from __future__ import annotations

from collections import Counter
from typing import Dict, List

from .models import (
    ClaimCheck,
    Evidence,
    IndustryAnalysis,
    RepoInsight,
    Repository,
)

# Human-maintained industry framing for recurring categories. It only interprets
# capabilities explicitly present in GitHub project metadata; it does not claim
# customer adoption, revenue, funding, or research novelty.
PROFILES: Dict[str, tuple] = {
    "pascalorg/editor": (
        "空间设计与创作工具", ["建筑设计师", "空间方案沟通者"],
        "三维建筑方案制作和分享门槛高，客户难以直观参与讨论。",
        "提供可创建和分享三维建筑项目的产品。",
        "浏览器中的三维空间协作", "让非专业参与者也能查看和讨论空间方案。",
        "专业能力、格式兼容性和商业模式尚待核实。",
    ),
    "jenkinsci/jenkins": (
        "企业自动化基础设施", ["数字产品团队", "企业 IT 部门"],
        "产品更新包含大量重复检查和发布步骤，人工操作容易出错。",
        "自动执行产品构建、测试和发布流程。",
        "成熟的自动化流水线", "AI 生成成果仍需可靠检查后才能进入生产环境。",
        "成熟系统可能伴随维护复杂度和历史配置负担。",
    ),
    "moeru-ai/airi": (
        "AI 伴侣与数字角色", ["数字娱乐用户", "游戏玩家"],
        "现有助手缺少持续人格、实时陪伴和跨场景互动。",
        "提供用户自己掌控、支持实时语音和游戏互动的虚拟角色。",
        "实时语音与可行动数字角色", "AI 产品从回答问题走向陪伴和参与活动。",
        "长期留存、情感依赖、内容安全和使用门槛仍需验证。",
    ),
    "andrewyng/aisuite": (
        "多模型应用基础设施", ["AI 产品团队", "采用多家模型的企业"],
        "不同模型供应商的接入方式不一致，切换和比较成本高。",
        "用统一方式接入多家生成式 AI 服务。",
        "多模型统一接入层", "竞争焦点转向模型组合、路由和治理。",
        "统一接口可能掩盖各模型独有能力。",
    ),
    "affaan-m/ECC": (
        "AI 智能体工作系统", ["使用 AI 助手的团队", "AI 工具产品团队"],
        "智能体容易遗忘经验、重复犯错，任务质量与安全性不稳定。",
        "把技能、记忆、安全规则和研究流程组合为智能体工作框架。",
        "可积累经验的智能体框架", "关注点从模型能力转向长期工作与受控执行。",
        "效果主张仍需独立基准和真实团队案例验证。",
    ),
    "hello245m/free-stockdb": (
        "金融数据与量化研究", ["量化研究者", "AI 金融产品团队"],
        "A 股历史与分钟数据获取、整理和重复查询成本较高。",
        "提供可本地同步、缓存、查询和回测的市场数据工具。",
        "本地优先的金融数据接口", "降低金融智能体连接结构化市场数据的门槛。",
        "数据授权、完整性、复权准确性和实时性需要独立核验。",
    ),
    "huggingface/speech-to-speech": (
        "实时语音智能体", ["语音产品团队", "客服与助理产品"],
        "自然语音交互常受延迟、云服务成本和隐私限制影响。",
        "使用开源模型构建可本地运行的语音智能体。",
        "本地端到端语音智能体", "语音 AI 可成为设备侧、可定制的交互入口。",
        "设备性能、噪声、语言覆盖和对话稳定性决定实际体验。",
    ),
    "virgiliojr94/book-to-skill": (
        "知识转化与智能体技能", ["知识工作者", "培训团队"],
        "专业书籍难以在实际任务中即时检索和应用。",
        "把技术书籍 PDF 转成智能体可调用的技能资料。",
        "从长文档到可调用技能", "知识管理从保存资料转向在任务中调用资料。",
        "版权、解析准确性、断章取义和知识过时是主要风险。",
    ),
    "opengeos/GeoLibre": (
        "地理空间分析产品", ["城市规划人员", "环境研究人员"],
        "传统地理工具安装复杂、跨设备协作困难且可能要求上传数据。",
        "提供跨浏览器、桌面、移动端和研究环境的轻量地理分析产品。",
        "本地处理与跨端地理可视化", "空间数据更容易进入 AI 与业务决策流程。",
        "大规模性能、专业功能深度和组织协作能力仍需验证。",
    ),
    "paperswithbacktest/awesome-systematic-trading": (
        "金融研究知识生态", ["量化研究者", "金融学习者"],
        "系统化交易资料分散，筛选学习路径和工具成本高。",
        "整理交易策略、工具、书籍和教程的资源目录。",
        "知识资源聚合", "反映金融研究与自动化交易仍受持续关注。",
        "资源收录和历史回测都不代表未来收益。",
    ),
    "microsoft/agent-governance-toolkit": (
        "AI 智能体治理与安全", ["企业安全团队", "合规负责人"],
        "自主智能体可能越权、泄露数据或执行危险操作。",
        "提供策略执行、零信任身份、隔离运行和可靠性治理工具。",
        "智能体零信任与执行隔离", "竞争从能不能做转向能否被企业安全地允许去做。",
        "治理工具不能自动解决错误决策，且需要接入企业现有体系。",
    ),
    "yorukot/superfile": (
        "个人生产力工具", ["管理大量本地文件的专业用户"],
        "大量本地文件的浏览和整理效率低。",
        "提供现代化文件管理体验。",
        "无特别 AI 技术", "对 AI 行业主要是本地文件工作流入口。",
        "与 AI 行业关联较弱，热度不能解读为 AI 趋势。",
    ),
    "bradautomates/claude-video": (
        "多模态内容理解", ["内容研究人员", "培训与媒体团队"],
        "文本助手无法直接理解长视频中的画面与语音信息。",
        "把视频拆解为画面和文字材料交给 AI 助手分析。",
        "视频、转写与大模型理解的组合", "视频可转成可搜索、可总结的工作材料。",
        "画面抽样遗漏、转写错误、成本、版权和隐私需要关注。",
    ),
}


def build_fallback_analysis(
    repositories: List[Repository], model_error: str
) -> IndustryAnalysis:
    insights: List[RepoInsight] = []
    for repo in repositories:
        direction, users, problem, solution, technology, impact, risk = PROFILES.get(
            repo.full_name,
            (
                "其他开发者关注方向", ["相关行业从业者"],
                repo.description or "公开资料不足，待进一步判断。",
                repo.description or "公开资料不足。",
                "公开资料不足", "暂不判断行业影响。",
                "证据不足，不能推断市场价值。",
            ),
        )
        scenarios = [
            f"{users[0]}在日常工作中使用该产品处理相关任务",
            "团队先用小范围试点验证效果，再决定是否扩大采用",
        ]
        benefits = ["减少重复工作或沟通成本", "让相关能力更容易进入实际工作流程"]
        insights.append(
            RepoInsight(
                full_name=repo.full_name,
                one_line_summary=solution,
                industry_direction=direction,
                target_users=users,
                problem_solved=problem,
                solution=solution,
                why_now=(
                    f"该项目位列当日 Trending 第 {repo.rank} 名，"
                    f"当日新增 {repo.stars_today} Star；这只代表开发者关注信号。"
                ),
                noteworthy_technology=technology,
                technology_impact=impact,
                product_form="开源项目或工具",
                commercialization_signal="没有足够一手资料证明收入、客户采用或融资。",
                maturity="需结合正式版本、用户案例和长期维护情况判断",
                risks=risk,
                ai_relevance=impact,
                plain_language_explanation=(
                    f"通俗地说：{problem} 这个项目尝试用“{solution}”来降低门槛。"
                ),
                scenario_examples=scenarios,
                practical_benefits=benefits,
                industry_implications=impact,
                who_should_care="、".join(users),
                validation_signals=[
                    "是否出现可核实的真实用户案例",
                    "是否连续多日或多周保持关注",
                    "是否发布清晰路线和稳定版本",
                ],
                claim_checks=[
                    ClaimCheck(
                        claim=f"项目位列当日 Trending 第 {repo.rank} 名",
                        claim_type="已验证事实",
                        source_kind="github_metadata",
                        source_excerpt="",
                        source_url=repo.url,
                        verification_status="结构化数据核对",
                    ),
                    ClaimCheck(
                        claim=repo.description or "项目没有提供简介",
                        claim_type="已验证事实",
                        source_kind="github_metadata",
                        source_excerpt="",
                        source_url=repo.url,
                        verification_status="GitHub 项目资料核对",
                    ),
                ],
                confidence="中" if repo.full_name in PROFILES else "低",
                priority_score=max(25, 100 - repo.rank * 3),
                evidence=[
                    Evidence("GitHub 项目资料", repo.url, "project")
                ],
            )
        )

    counts = Counter(item.industry_direction for item in insights)
    ai_count = sum(
        "AI" in item.industry_direction
        or "智能体" in item.industry_direction
        or "语音" in item.industry_direction
        or "多模态" in item.industry_direction
        for item in insights
    )
    return IndustryAnalysis(
        available=True,
        error=(
            "模型不可用，已用项目资料、确定性数据与人工维护的行业框架生成；"
            f"未进行外部网页研究。原始错误：{model_error}"
        ),
        key_judgments=[
            f"至少 {ai_count}/{len(insights)} 个项目直接涉及智能体、语音、"
            "多模态或 AI 应用基础设施。",
            "智能体热点从“完成任务”转向记忆、安全、身份、权限和可靠运行。",
            "本地优先跨语音、金融数据和地理空间产品出现，价值是降低云依赖并增强数据控制。",
            "金融领域同时出现数据底座和研究资源，开发者正在补齐 AI 金融应用的资料工具层。",
            "连续留榜的 AI 伴侣与视频理解项目显示，多模态交互仍比单纯文本问答更吸引注意。",
        ],
        hot_characteristics=[
            f"{name}（{count} 个项目）" for name, count in counts.most_common(6)
        ],
        product_business_signals=[
            "企业智能体机会正向治理、安全和多模型管理迁移。",
            "消费 AI 开始强调实时语音、持续角色和参与具体活动。",
            "本地运行与用户掌控数据成为多个应用方向的共同卖点。",
            "多数项目仍处于开源关注阶段，不能推断付费采用或商业成功。",
        ],
        watch_next=[
            "观察智能体治理项目是否出现企业集成案例。",
            "观察实时语音智能体在普通设备上的延迟和中文体验。",
            "观察 AI 伴侣与视频理解项目能否持续留榜并形成用户留存。",
            "核实金融数据工具的数据授权、准确性和商业使用边界。",
        ],
        repositories=insights,
    )
