from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Tuple

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


# Ordered from specific to broad.  These rules are deliberately written in
# business language: the fallback must remain useful when the free model is
# unavailable, instead of copying an English repository description into every
# field.  A rule is only selected when its keywords occur in repository-owned
# metadata (description, topics or README excerpt).
CATEGORY_RULES: List[Tuple[List[str], tuple]] = [
    (["authentik", "identity provider", "single sign-on", " sso "], (
        "企业身份与访问管理", ["企业 IT 与安全团队", "管理内部系统权限的负责人"],
        "企业应用增多后，员工登录、权限回收和访问审计容易分散失控。",
        "集中管理身份认证、单点登录和应用访问权限。",
        "统一身份与访问控制", "它不是新的 AI 技术，但可能成为企业控制 AI 工具访问权限的底座。",
        "配置错误可能造成越权或账号无法访问，迁移与运维成本需要评估。",
        "例如员工离职时，企业可以在一个地方回收其多个应用的访问权限。",
        ["减少分散管理账号和权限的工作", "提高访问审计与离职权限回收的可控性"],
    )),
    (["daily_stock", "stock analysis", "systematic trading"], (
        "AI 金融研究助手", ["个人投资研究者", "金融内容与研究团队"],
        "市场资料分散，日常研究需要重复收集行情、事件和公司信息。",
        "用自动化或 AI 工作流整理每日市场信息并形成研究线索。",
        "自动化金融研究流程", "AI 正被用于压缩资料整理时间，但不能代替投资判断。",
        "数据错误、时效、过度自信和缺少合规边界可能导致错误投资决策。",
        "例如研究者每天开盘前汇总关注公司的价格变化、公告和风险提示。",
        ["减少重复搜集市场资料的时间", "让研究过程更有固定结构和可追溯线索"],
    )),
    (["harvey", "legal ai", "legal research", "law"], (
        "法律 AI 与专业服务研究", ["律师事务所与法务团队", "法律 AI 产品负责人"],
        "法律资料量大且错误成本高，通用模型难以直接满足专业准确性要求。",
        "开放法律 AI 的研究、评测或实验成果，帮助行业判断能力边界。",
        "专业领域 AI 评测", "法律 AI 的竞争重点是可靠证据、专业流程和责任边界，而非通用问答。",
        "法律结论必须由专业人员复核，并关注保密、地域法律差异和责任归属。",
        "例如法务团队先用它整理案件资料，再由律师核对引用和判断。",
        ["帮助专业团队更快筛选资料", "让法律 AI 的能力和限制更容易被公开检验"],
    )),
    (["weather", "forecast", "climate"], (
        "AI 天气与气候预测", ["气象机构", "能源、农业和保险决策团队"],
        "传统高精度天气预测计算昂贵，极端天气的不确定性又直接影响业务决策。",
        "利用机器学习模型更快地产生天气预测和概率判断。",
        "AI 概率天气预测", "更快、更细的预测可能让高风险行业更早调整计划。",
        "预测偏差会带来真实决策风险，必须与官方预报和历史回测共同验证。",
        "例如能源团队提前判断风电供给变化，保险团队评估极端天气暴露。",
        ["缩短预测等待时间", "帮助团队更早准备库存、调度或风险预案"],
    )),
    (["code graph", "knowledge graph", "graph rag", "monorepo", "codebase"], (
        "AI 软件知识与代码理解", ["大型软件团队", "技术管理者和代码审查团队"],
        "大型软件系统关系复杂，新成员和 AI 助手难以理解修改会影响哪里。",
        "把代码关系组织成可查询的知识图谱，再让 AI 基于这些关系回答和修改。",
        "代码知识图谱与检索增强", "AI 编程正在从读单个文件走向理解整个产品系统。",
        "错误的依赖关系可能让 AI 给出看似合理但会破坏系统的修改建议。",
        "例如团队接手旧系统时，先询问某项功能涉及哪些模块和依赖。",
        ["减少理解大型系统所需的人工查找", "降低跨模块修改遗漏影响范围的概率"],
    )),
    ([
        "coding agent", "code agent", "coding workflow", "software engineering",
        "agent skill", "t3code",
    ], (
        "AI 编程智能体", ["软件产品团队", "管理 AI 开发效率的技术负责人"],
        "AI 能生成代码，但长任务中容易丢失目标、重复犯错或交付不可用结果。",
        "为编程智能体提供可持续执行、专业技能或自我改进的工作机制。",
        "可持续执行与技能化智能体", "AI 编程竞争正从单次生成速度转向长任务完成质量。",
        "自我改进和长时间自动执行可能放大错误，仍需要权限限制和人工验收。",
        "例如把一项跨多文件的产品改动交给智能体持续完成，并在关键步骤由人确认。",
        ["减少工程师在重复修改与资料查找上的时间", "让复杂开发任务更容易形成可审查的交付过程"],
    )),
    (["agent", "multi-agent", "autonomous", "agency"], (
        "AI 智能体与数字劳动力", ["希望自动化知识工作的企业团队", "AI 产品与运营负责人"],
        "通用聊天助手只能给建议，难以分工并持续完成跨步骤工作。",
        "把不同角色、工具、记忆和流程组合为能协作执行任务的智能体。",
        "多角色智能体协作", "AI 产品正在从对话入口转向可管理的工作执行系统。",
        "角色描述不等于真实专业能力，多智能体还会增加成本、延迟和责任边界问题。",
        "例如市场团队让研究、写作和审核智能体协作完成一次内容策划。",
        ["把多步骤工作拆成清晰分工", "减少人员在不同工具之间传递资料和跟进状态的负担"],
    )),
    (["rag", "retrieval", "search", "knowledge"], (
        "企业知识检索与 RAG", ["知识密集型企业", "客服、研究和内部运营团队"],
        "资料分散时，员工和 AI 助手难以找到可靠、可追溯的答案。",
        "先检索相关资料，再让 AI 基于找到的内容回答或执行。",
        "检索增强生成", "企业采用 AI 的重点正在转向连接自己的可信资料。",
        "检索遗漏和过期资料仍会导致错误答案，来源与更新时间必须可见。",
        "例如客服人员提问后，系统从最新产品文档中找到依据再组织回复。",
        ["减少跨文档搜索时间", "让回答更容易追溯到企业自己的资料"],
    )),
    (["voice", "speech", "audio"], (
        "语音 AI 与自然交互", ["客服与销售团队", "需要免手操作的普通用户"],
        "键盘和复杂界面限制了 AI 在移动、驾驶和实时服务中的使用。",
        "通过语音理解、生成或语音指令把 AI 带入实时工作场景。",
        "实时语音交互", "语音可能成为比聊天框更自然的 AI 使用入口。",
        "口音、噪声、隐私和错误执行会直接影响体验与信任。",
        "例如销售人员在路上口述客户记录，系统整理后等待确认。",
        ["减少打字和手动录入", "让 AI 能进入移动和实时服务场景"],
    )),
    (["video", "vision", "image", "multimodal", "comfyui"], (
        "多模态内容理解", ["内容、教育和媒体团队", "需要处理图片或视频的业务团队"],
        "大量视觉和视频内容难以被快速搜索、总结和复用。",
        "让 AI 同时处理画面、语音和文字并形成可使用的信息。",
        "视觉与语言联合理解", "企业资料不再局限于文本，视频和图片也能进入知识工作流。",
        "抽帧、转写和视觉识别错误可能遗漏关键内容，还需关注版权与隐私。",
        "例如培训团队把长视频转成带出处的要点和复习材料。",
        ["缩短观看和整理长视频的时间", "让视觉资料可以被搜索和再次利用"],
    )),
    (["security", "governance", "permission", "identity", "sandbox"], (
        "AI 安全、权限与治理", ["企业安全与合规负责人", "准备部署智能体的组织"],
        "智能体连接真实数据和系统后，可能越权、泄露信息或执行危险操作。",
        "通过身份、权限、隔离和审计机制限制智能体可以做什么。",
        "智能体零信任治理", "企业购买 AI 的前提正从能力演示转向可控和可追责。",
        "治理工具不能消除模型判断错误，组织仍需明确审批与责任人。",
        "例如智能体可以起草退款操作，但超过额度必须由员工批准。",
        ["降低智能体误操作的影响范围", "让企业更容易审计谁在何时执行了什么"],
    )),
    (["finance", "trading", "stock", "market data"], (
        "AI 金融数据与研究", ["金融研究与投资团队", "金融 AI 产品团队"],
        "市场数据和研究资料分散，获取、清洗与验证成本较高。",
        "提供可查询的数据、研究资料或分析工作流供人和 AI 使用。",
        "金融数据工具化", "金融 AI 的价值越来越依赖稳定、合规且可追溯的数据底座。",
        "数据许可、延迟、历史偏差和回测过拟合都可能造成错误判断。",
        "例如研究人员快速比较某类资产的历史表现，再人工检查数据口径。",
        ["减少收集和整理金融资料的时间", "提高研究过程的可重复性和可追溯性"],
    )),
    (["process", "port", "container", "debug", "trace", "observability"], (
        "软件运行诊断工具", ["维护数字产品的技术团队", "负责系统稳定性的运维人员"],
        "系统出现异常时，很难快速追溯某个进程、服务或文件由什么启动。",
        "把运行中的对象与其来源关系整理出来，帮助团队定位问题。",
        "运行关系追踪", "它不是 AI 突破，但能降低复杂自动化系统的排障成本。",
        "主要服务技术团队，与 AI 行业的直接商业关联有限。",
        "例如线上服务异常占用资源时，快速找到启动它的任务和负责人。",
        ["缩短故障定位时间", "减少误关关键服务或反复排查的风险"],
    )),
]


def _rule_profile(repo: Repository) -> tuple:
    if repo.full_name in PROFILES:
        base = PROFILES[repo.full_name]
        return (*base, f"例如{base[1][0]}把该能力用于真实工作任务，并在小范围内验证。",
                [base[5], "降低采用相关能力的操作门槛"])
    text = " ".join([
        repo.full_name, repo.description, " ".join(repo.topics)
    ]).lower()
    for keywords, profile in CATEGORY_RULES:
        if any(keyword in text for keyword in keywords):
            return profile
    subject = re.sub(r"[-_/]+", " ", repo.full_name.split("/")[-1]).strip()
    return (
        "其他数字产品与工具", ["评估数字工具的产品负责人"],
        "项目资料显示它在解决一个具体工作问题，但与 AI 行业的直接关系尚不明确。",
        f"提供名为 {subject} 的开源工具或资料。",
        "未发现可确认的特殊 AI 技术", "不应仅因进入 GitHub 热榜就解读为 AI 行业趋势。",
        "资料有限，需核实真实用户、维护稳定性和具体效果。",
        "例如产品团队先确认它是否适用于自己的流程，再进行小范围试用。",
        ["为特定工作提供新的工具选择", "帮助团队比较现有方案是否仍然合适"],
    )


def build_fallback_analysis(
    repositories: List[Repository], model_error: str
) -> IndustryAnalysis:
    insights: List[RepoInsight] = []
    for repo in repositories:
        (direction, users, problem, solution, technology, impact, risk,
         scenario, benefits) = _rule_profile(repo)
        subject = repo.full_name.split("/")[-1]
        scenarios = [scenario]
        benefits = [f"对 {subject} 的潜在使用者而言，{benefits[0]}", *benefits[1:]]
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
                    f"通俗地说，{subject} 希望解决的是：{problem} "
                    f"它的办法是：{solution}"
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
                confidence="中" if direction != "其他数字产品与工具" else "低",
                priority_score=max(25, 100 - repo.rank * 3),
                evidence=[
                    Evidence("GitHub 项目资料", repo.url, "project")
                ],
            )
        )

    counts = Counter(item.industry_direction for item in insights)
    ai_count = sum(any(word in item.industry_direction for word in
                       ["AI", "智能体", "语音", "多模态", "知识检索"])
                   for item in insights)
    leading = counts.most_common(3)
    leading_text = "、".join(f"{name}（{count} 个）" for name, count in leading)
    non_ai = len(insights) - ai_count
    lead_name = insights[0].full_name if insights else "项目"
    lead_direction = insights[0].industry_direction if insights else "未知方向"
    lead_theme = leading[0][0] if leading else "主要方向"
    return IndustryAnalysis(
        available=True,
        error=(
            "模型不可用，已用项目资料、确定性数据与人工维护的行业框架生成；"
            f"未进行外部网页研究。原始错误：{model_error}"
        ),
        key_judgments=[
            f"当日 {ai_count}/{len(insights)} 个项目可从资料确认与 AI 直接相关；"
            f"其余 {non_ai} 个不应被包装成 AI 趋势。",
            f"开发者关注主要集中在：{leading_text or '尚未形成集中方向'}。",
            f"排名第一的 {lead_name} 代表“{lead_direction}”受到显著关注，"
            "但热度仍不等于商业采用。",
            "多个项目的价值不在模型参数更大，而在让 AI 能理解业务资料、"
            "持续执行或进入具体工作场景。",
            "今天最需要验证的不是演示效果，而是真实用户是否持续使用、错误是否可控以及是否形成清晰付费价值。",
        ],
        hot_characteristics=[
            f"{name}（{count} 个项目）" for name, count in counts.most_common(6)
        ],
        product_business_signals=[
            f"{lead_theme}是今天最集中的供给方向，"
            "适合继续观察是否出现真实客户案例。",
            "开源热度可用于发现需求和竞争者，但不能代替收入、留存、部署量或研究评测。",
            "能进入现有工作流、减少明确成本并提供可控结果的项目，更可能形成产品机会。",
        ],
        watch_next=[
            f"观察 {lead_theme} 是否连续多日出现，而不是单日项目爆发。",
            "优先寻找项目方公布的真实使用案例、稳定版本和可重复评测。",
            "核实高热项目的许可证、数据来源、隐私和企业使用边界。",
        ],
        repositories=insights,
    )
