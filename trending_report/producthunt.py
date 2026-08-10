from __future__ import annotations

import html
import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

from .clients import HTTPClient, OpenAIClient

PRODUCT_HUNT_API = "https://api.producthunt.com/v2/api/graphql"
PRODUCT_HUNT_SOURCE = "https://www.producthunt.com/"
ANALYSIS_VERSION = 2

POSTS_QUERY = """
query DailyPosts($after: DateTime!, $before: DateTime!) {
  posts(
    first: 40
    featured: true
    order: RANKING
    postedAfter: $after
    postedBefore: $before
  ) {
    nodes {
      id name slug tagline description url website dailyRank
      votesCount commentsCount createdAt featuredAt
      thumbnail { url }
      topics(first: 10) { nodes { name slug } }
      makers { name username }
      productLinks { type url }
    }
  }
}
"""

PRODUCT_PROPERTIES: Dict[str, Any] = {
    "slug": {"type": "string"},
    "category": {"type": "string"},
    "what_it_sells": {"type": "string"},
    "target_customers": {"type": "array", "items": {"type": "string"}},
    "problem_solved": {"type": "string"},
    "plain_scenario": {"type": "string"},
    "benefits": {"type": "array", "items": {"type": "string"}},
    "pricing_model": {"type": "string"},
    "conversion_path": {"type": "string"},
    "positioning": {"type": "string"},
    "acquisition_hypothesis": {"type": "string"},
    "differentiation": {"type": "string"},
    "ai_role": {"type": "string"},
    "maturity": {"type": "string"},
    "risks": {"type": "string"},
    "confidence": {"type": "string", "enum": ["高", "中", "低"]},
    "fact_claims": {
        "type": "array",
        "items": {
            "type": "object",
            "additionalProperties": False,
            "required": ["claim", "source_url", "source_excerpt"],
            "properties": {
                "claim": {"type": "string"},
                "source_url": {"type": "string"},
                "source_excerpt": {"type": "string"},
            },
        },
    },
    "strategy_judgments": {"type": "array", "items": {"type": "string"}},
}

PRODUCT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "key_judgments",
        "buying_capabilities",
        "customer_patterns",
        "business_model_patterns",
        "new_product_forms",
        "products",
    ],
    "properties": {
        "key_judgments": {
            "type": "array",
            "minItems": 3,
            "maxItems": 5,
            "items": {"type": "string"},
        },
        "buying_capabilities": {"type": "array", "items": {"type": "string"}},
        "customer_patterns": {"type": "array", "items": {"type": "string"}},
        "business_model_patterns": {"type": "array", "items": {"type": "string"}},
        "new_product_forms": {"type": "array", "items": {"type": "string"}},
        "products": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": list(PRODUCT_PROPERTIES),
                "properties": PRODUCT_PROPERTIES,
            },
        },
    },
}


@dataclass
class SourcePage:
    url: str
    title: str
    excerpt: str
    kind: str


@dataclass
class Product:
    id: str
    rank: int
    slug: str
    name: str
    tagline: str
    description: str
    product_hunt_url: str
    website: str
    votes_count: int
    comments_count: int
    created_at: str
    featured_at: str
    thumbnail: str = ""
    topics: List[str] = field(default_factory=list)
    makers: List[str] = field(default_factory=list)
    product_links: List[Dict[str, str]] = field(default_factory=list)
    source_pages: List[SourcePage] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["source_pages"] = [asdict(item) for item in self.source_pages]
        return result


def latest_complete_day(now: Optional[datetime] = None) -> date:
    local = (now or datetime.now(tz=ZoneInfo("UTC"))).astimezone(
        ZoneInfo("America/Los_Angeles")
    )
    return local.date() - timedelta(days=1)


def day_bounds(report_date: date) -> tuple[str, str]:
    timezone = ZoneInfo("America/Los_Angeles")
    start = datetime.combine(report_date, time.min, timezone)
    return start.isoformat(), (start + timedelta(days=1)).isoformat()


class ProductHuntClient:
    def __init__(self, token: str, http: Optional[HTTPClient] = None) -> None:
        # Tokens are continuous strings, but dashboard copies can introduce
        # invisible whitespace (including an internal line break).
        self.token = re.sub(r"\s+", "", token)
        self.http = http or HTTPClient(retries=3, timeout=30)

    def fetch_daily(self, report_date: date, limit: int = 15) -> List[Product]:
        if not self.token:
            raise RuntimeError(
                "未配置 PRODUCT_HUNT_TOKEN，不能使用 Product Hunt 官方 API"
            )
        after, before = day_bounds(report_date)
        payload = {
            "query": POSTS_QUERY,
            "variables": {"after": after, "before": before},
        }
        body = self.http.request(
            PRODUCT_HUNT_API,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            data=json.dumps(payload).encode("utf-8"),
        )
        response = json.loads(body.decode("utf-8"))
        if response.get("errors"):
            message = response["errors"][0].get("message", "GraphQL 请求失败")
            raise RuntimeError(f"Product Hunt API 错误：{message}")
        nodes = response.get("data", {}).get("posts", {}).get("nodes", [])
        products = [self._product(node) for node in nodes]
        products = [item for item in products if item.rank > 0]
        products.sort(key=lambda item: item.rank)
        return products[:limit]

    @staticmethod
    def _product(node: Dict[str, Any]) -> Product:
        topics = node.get("topics", {}).get("nodes", [])
        links = [
            {"type": str(item.get("type", "")), "url": str(item.get("url", ""))}
            for item in node.get("productLinks", [])
            if item.get("url")
        ]
        return Product(
            id=str(node.get("id", "")),
            rank=int(node.get("dailyRank") or 0),
            slug=str(node.get("slug", "")),
            name=str(node.get("name", "")),
            tagline=str(node.get("tagline", "")),
            description=str(node.get("description") or ""),
            product_hunt_url=str(node.get("url", "")),
            website=str(node.get("website", "")),
            votes_count=int(node.get("votesCount") or 0),
            comments_count=int(node.get("commentsCount") or 0),
            created_at=str(node.get("createdAt", "")),
            featured_at=str(node.get("featuredAt") or ""),
            thumbnail=str((node.get("thumbnail") or {}).get("url", "")),
            topics=[str(item.get("name", "")) for item in topics if item.get("name")],
            makers=[
                str(item.get("name") or item.get("username") or "")
                for item in node.get("makers", [])
                if item.get("name") or item.get("username")
            ],
            product_links=links,
        )


class OfficialSiteReader:
    def __init__(self, http: Optional[HTTPClient] = None) -> None:
        self.http = http or HTTPClient(retries=2, timeout=15)

    def enrich(self, product: Product) -> Product:
        homepage = self._read(product.website, "官网")
        if homepage:
            product.source_pages.append(homepage)
            pricing_url = self._pricing_url(product.website, homepage.excerpt)
            if pricing_url and pricing_url != product.website:
                pricing = self._read(pricing_url, "价格页")
                if pricing:
                    product.source_pages.append(pricing)
        return product

    def _read(self, url: str, kind: str) -> Optional[SourcePage]:
        if not _safe_public_url(url):
            return None
        try:
            body = self.http.request(
                url,
                headers={"Accept": "text/html,application/xhtml+xml"},
            )
        except Exception:
            return None
        text = body.decode("utf-8", errors="replace")
        title_match = re.search(
            r"<title[^>]*>(.*?)</title>", text, flags=re.I | re.S
        )
        title = _clean_html(title_match.group(1)) if title_match else kind
        cleaned = _clean_html(
            re.sub(r"<(script|style|svg)[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
        )
        return SourcePage(url=url, title=title[:160], excerpt=cleaned[:8_000], kind=kind)

    @staticmethod
    def _pricing_url(base_url: str, excerpt: str) -> str:
        del excerpt
        parsed = urlparse(base_url)
        return urljoin(f"{parsed.scheme}://{parsed.netloc}/", "pricing")


def _safe_public_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        return False
    return not (
        host in {"localhost", "0.0.0.0"}
        or host.startswith("127.")
        or host.startswith("10.")
        or host.startswith("192.168.")
        or host.endswith(".local")
    )


def _clean_html(value: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())


PRODUCT_RULES = [
    (["product drift", "ai-written code", "prelint"],
     "AI 生成软件的质量控制", ["使用 AI 开发产品的团队", "产品与工程负责人"],
     "在 AI 快速改代码后，检查产品行为是否偏离原定需求和规则。",
     ["更早发现 AI 修改造成的产品偏差", "减少速度提升后返工和验收成本反而上升的问题"],
     "AI 是被治理的生产工具；产品价值在于检查 AI 生成结果是否仍符合业务要求。"),
    (["music tutor", "guitar", "playing"],
     "AI 音乐陪练", ["吉他学习者", "希望提供课后练习的音乐教师"],
     "用户练琴时获得实时反馈，而不必等到下一次线下课程。",
     ["缩短动作与反馈之间的等待", "让个人练习更有方向并容易保持频率"],
     "AI 是实时听辨和反馈能力，但不能完全替代教师对姿势与长期学习计划的判断。"),
    (["vibe-coded", "paying customers", "app into"],
     "独立应用商业化", ["用 AI 做出应用的独立创作者", "缺少营销经验的小型产品团队"],
     "产品做出来后仍不知道怎样定位、获客并转化为付费客户。",
     ["把注意力从继续开发转向验证付费需求", "降低独立创作者设计销售路径的门槛"],
     "AI 可能辅助商业建议，但核心价值是产品营销与转化方法。"),
    (["spawn a team", "give claude code missions", "team of agents"],
     "AI 开发任务编排", ["同时使用多个编程智能体的开发团队", "管理复杂开发任务的负责人"],
     "单个编程智能体难以独立覆盖规划、执行和检查等多种角色。",
     ["把大型开发任务拆给多个角色协作", "让负责人更容易查看任务进度和交付边界"],
     "AI 智能体是核心执行者，产品负责分工和协同。"),
    (["hipaa", "healthcare", "clinic", "medical"],
     "医疗记录与临床工作助手", ["医疗机构和临床工作人员", "重视合规的医疗运营团队"],
     "临床沟通和记录耗时，同时包含高度敏感的患者信息。",
     ["减少医务人员整理记录的时间", "在明确合规边界下改善资料回顾和交接"],
     "AI 可辅助记录与整理，但医疗判断、隐私、HIPAA 合规和错误责任必须由机构验证。"),
    (["repo-native memory", "memory for coding agents", "coding agents"],
     "编程智能体记忆与流程管理", ["长期使用编程智能体的软件团队", "希望保留项目上下文的开发者"],
     "智能体跨任务后容易忘记项目约定、历史决定和上次工作进度。",
     ["减少每次任务重复解释项目背景", "降低智能体因遗忘约定而重复犯错的概率"],
     "AI 智能体是使用者，产品提供可保存和审查的项目记忆。"),
    (["bookmarks", "twitter", "make you read"],
     "个人信息整理与阅读", ["收藏大量社交内容的知识工作者", "研究和内容创作者"],
     "收藏内容不断堆积，却缺少整理和重新阅读的机制。",
     ["把零散收藏变成可回顾的主题", "提高已收藏信息真正被阅读和使用的概率"],
     "AI 可辅助分类与摘要，但产品核心价值是信息整理和阅读习惯。"),
    (["assistant", "lives in your texts", "text messages"],
     "消息入口的个人 AI 助手", ["希望在手机消息中直接使用 AI 的普通用户"],
     "用户不想为了简单任务反复打开新的 AI 应用和学习复杂界面。",
     ["在熟悉的消息入口直接获得帮助", "减少应用切换并降低 AI 使用门槛"],
     "AI 是核心服务能力；消息隐私、身份验证和错误操作是关键风险。"),
    (["recruiting coordinator", "hiring", "interview"],
     "招聘流程自动化", ["招聘团队", "需要大量安排候选人沟通的成长型企业"],
     "候选人沟通、面试安排和状态跟进占用招聘人员大量时间。",
     ["减少面试排期和重复跟进", "让招聘人员把时间放在候选人判断与沟通质量上"],
     "AI 可承担协调和信息整理，但不应在缺乏监督时决定候选人的公平机会。"),
    (["video feedback", "editors", "clients"],
     "视频审阅与客户反馈", ["视频编辑者", "需要审批视频的客户和营销团队"],
     "视频修改意见分散在聊天和邮件中，时间点与版本难以对应。",
     ["让反馈直接对应视频位置", "减少编辑者确认版本和解释修改意见的时间"],
     "AI 不是核心能力；产品价值是审阅协作与版本沟通。"),
    (["usage", "menu bar", "mission control", "claude code & codex"],
     "AI 工具使用监控", ["高频使用 Claude、Codex 或 Cursor 的个人和团队"],
     "多个 AI 工具的使用量、任务状态和成本不容易在一个地方掌握。",
     ["更快看清 AI 工具的使用状态", "帮助用户避免额度耗尽或任务失去跟踪"],
     "AI 不是产品本身的核心能力；它负责观察和管理其他 AI 工具。"),
    (["terminal", "libghostty", "command line"],
     "桌面终端工具", ["需要命令行工作的技术用户"],
     "用户希望获得更轻量、原生且稳定的命令行工作环境。",
     ["改善高频命令行操作体验", "提供另一种本地开发工具选择"],
     "AI 不是核心能力，与 AI 行业的关系主要是可作为智能体工具入口。"),
    (["body-focused", "hair pulling", "skin picking", "nail biting"],
     "行为健康自助工具", ["受拔毛、咬甲或皮肤抓挠困扰的人"],
     "在冲动出现时记录诱因并完成短小练习，逐步减少重复行为。",
     ["让用户更容易发现行为触发因素", "用低压力的小目标帮助用户坚持行为训练"],
     "AI 不是产品成立的必要条件；核心价值是行为训练与持续记录。"),
    (["proxy", "scraping", "success rate", "latency"],
     "数据采集基础设施评测", ["数据采集团队", "SaaS 与 AI 数据产品团队"],
     "采购代理服务前，用自己的目标网站比较不同方案的成功率、速度和成本。",
     ["减少只依据供应商宣传做采购决定的风险", "更快找到适合特定网站的数据采集方案"],
     "AI 不是核心能力，但 AI 产品的数据采集团队可能使用它。"),
    (["conference", "sponsor", "exhibit", "speaker"],
     "B2B 市场与销售情报", ["B2B 市场团队", "销售拓展与合作团队"],
     "准备会议营销时，查询目标公司参加、赞助或演讲过的活动。",
     ["减少人工搜集会议名单的时间", "帮助团队优先联系更可能参加行业活动的公司"],
     "AI 不是核心能力；产品价值来自结构化商业数据。"),
    (["macros", "calories", "protein", "meal", "nutrition"],
     "个人营养记录", ["健身与饮食管理用户", "不愿手工搜索食物数据库的人"],
     "吃完饭拍照或说一句话，快速记录热量、蛋白质、碳水和脂肪。",
     ["降低每餐手工录入的操作负担", "让营养记录更容易长期坚持"],
     "AI 主要辅助从照片或语音估算食物信息，最终数值仍需用户校正。"),
    (["personal crm", "contacts with context", "stay in touch"],
     "个人关系管理", ["需要长期维护客户与人脉的个人用户", "自由职业者和顾问"],
     "在手机联系人旁记录背景和跟进线索，避免忘记重要关系。",
     ["减少记忆人际背景的负担", "帮助用户更有规律地跟进重要联系人"],
     "未发现 AI 是核心能力；主要价值是联系人上下文和隐私友好的同步。"),
    (["storage", "disk", "file-type", "allocated space"],
     "存储空间分析", ["Mac 用户", "管理本地或云端大量文件的专业用户"],
     "电脑空间不足时，用表格快速找出真正占用空间的文件夹和文件类型。",
     ["缩短寻找大文件的时间", "降低误删文件和反复清理的成本"],
     "AI 不是核心能力；它是信息呈现和文件管理工具。"),
    (["docsalot", "documentation", "publish documentation", "docs site"],
     "AI 文档生产与维护", ["软件产品团队", "需要维护帮助中心或产品文档的团队"],
     "让 AI 把初稿整理成可发布的文档站，并在内容变化后持续更新。",
     ["减少排版、迁移和发布文档的重复工作", "让文档更新更容易跟上产品变化"],
     "AI 是核心执行者，负责创建和维护内容；人工审批决定最终发布。"),
    (["voice", "dictation", "say it", "speech"],
     "语音原生应用与操作", ["希望减少键盘操作的知识工作者", "需要免手操作的用户"],
     "用一句自然语言创建小应用或直接让电脑完成记录、发送和查询任务。",
     ["减少打字和在应用之间切换", "让非技术用户用说话的方式创建个性化工具"],
     "AI 是核心能力：负责理解语音意图、生成应用或把指令转成操作。"),
    (["creative agent", "creative workflows", "content", "creator"],
     "创意智能体工作系统", ["内容创作者", "社交媒体与创意团队"],
     "从一个创意目标出发，让不同智能体完成研究、制作、监控和修改。",
     ["减少创意项目中的跨工具协调", "让小团队覆盖原本需要多种专业角色的工作"],
     "AI 是核心生产能力，但成品质量、版权与品牌一致性仍需人工把关。"),
    (["agents work together", "agentconnect", "permissions", "workspace", "memory"],
     "企业多智能体协作", ["部署多个 AI 助手的企业团队", "AI 运营与安全负责人"],
     "在聊天、代码和任务系统中统一分配智能体角色、权限、记忆与工作空间。",
     ["减少团队管理多个智能体入口的混乱", "让智能体协作过程更可见、更可控"],
     "AI 是核心执行主体；平台价值在于连接、权限和协作治理。"),
    (["browser", "clicking", "filling forms", "gmail", "whatsapp"],
     "浏览器执行型智能体", ["需要处理大量网页事务的知识工作者", "销售、运营和行政团队"],
     "直接在用户已登录的网页中点击、填写表单并完成跨应用任务。",
     ["把 AI 的建议转化为实际完成的操作", "减少重复网页录入和跨系统搬运信息"],
     "AI 是核心决策和执行能力；账号权限、误操作和敏感数据是主要风险。"),
    (["prompt", "leaderboard", "puzzle", "golf"],
     "AI 提示词训练与娱乐", ["希望练习模型沟通的人", "AI 社区与教育活动组织者"],
     "通过限字数和禁用词的竞赛，练习怎样用更少指令得到目标输出。",
     ["用游戏方式理解模型对措辞的反应", "为 AI 社区提供可分享的挑战内容"],
     "AI 是游戏对象和核心机制，但产品本身不代表新的模型技术。"),
]


def _product_profile(product: Product) -> tuple:
    text = " ".join([
        product.name, product.tagline, product.description,
        " ".join(product.topics),
    ]).lower()
    for keywords, category, customers, scenario, benefits, ai_role in PRODUCT_RULES:
        if any(keyword in text for keyword in keywords):
            return category, customers, scenario, benefits, ai_role
    topic = product.topics[0] if product.topics else "数字产品"
    return (
        topic,
        [f"正在寻找 {product.name} 所代表的{topic}方案的个人或团队"],
        f"在出现“{product.tagline or product.name}”所描述的需求时，"
        f"用 {product.name} 完成一次具体任务。",
        [
            f"让用户可以直接试用 {product.name} 所提供的解决方式",
            "帮助用户比较是否能替代当前的手工流程",
        ],
        "根据现有资料无法确认 AI 是核心能力，不把营销标签当作技术事实。",
    )


def _pricing_and_conversion(product: Product) -> tuple:
    excerpt = " ".join(page.excerpt for page in product.source_pages)
    lower = excerpt.lower()
    prices = re.findall(
        r"(?:\$|€|£)\s?\d+(?:\.\d+)?(?:\s*/\s*(?:mo|month|yr|year))?",
        excerpt,
        re.I,
    )
    unique_prices = list(dict.fromkeys(value.replace(" ", "") for value in prices))[:3]
    if unique_prices:
        label = "官网公开价格：" + "、".join(unique_prices)
        if any(word in lower for word in ["contact sales", "talk to sales", "book a demo"]):
            return label + "；另有企业销售方案", "可自助购买，企业客户可联系销售"
        return label, "官网自助购买"
    if any(word in lower for word in ["free trial", "start trial", "try for free"]):
        return "官网提供免费试用，付费价格未确认", "先自助试用，再决定是否购买"
    if re.search(r"\bfree\b", lower):
        return "官网提供免费入口；是否有付费方案尚未确认", "官网自助开始使用"
    if any(word in lower for word in ["contact sales", "talk to sales", "book a demo"]):
        return "企业询价，具体价格未公开", "预约演示或联系销售"
    if any(word in lower for word in ["pricing", "per month", "/month"]):
        return "官网显示存在付费方案，具体价格未能可靠提取", "官网自助购买"
    return "未公开", "访问官网了解或开始使用"


def product_analysis_quality_errors(analysis: Dict[str, Any], expected: int) -> List[str]:
    products = analysis.get("products", [])
    errors: List[str] = []
    if len(products) != expected:
        errors.append("产品分析数量与榜单不一致")
    for field_name, label in [
        ("plain_scenario", "通俗场景"), ("benefits", "实际好处")
    ]:
        values = [json.dumps(item.get(field_name), ensure_ascii=False, sort_keys=True)
                  for item in products]
        if values and Counter(values).most_common(1)[0][1] > max(3, len(values) // 3):
            errors.append(f"{label}重复率过高")
    placeholders = ["需进一步核实", "可从产品官网进一步确认", "目标客户未公开"]
    if sum(any(word in json.dumps(item, ensure_ascii=False) for word in placeholders)
           for item in products) > max(3, expected // 3):
        errors.append("占位式分析过多")
    return errors


def _fallback_analysis(products: List[Product], error: str = "") -> Dict[str, Any]:
    topic_counts = Counter(topic for item in products for topic in item.topics)
    products_result = []
    for product in products:
        evidence = [
            {
                "claim": product.tagline or product.description or "产品定位未公开",
                "source_url": product.product_hunt_url,
                "source_excerpt": product.tagline or product.description,
            }
        ]
        pricing, conversion = _pricing_and_conversion(product)
        category, customers, scenario, benefits, ai_role = _product_profile(product)
        scenario = f"以 {product.name} 为例：{scenario}"
        benefits = [
            f"对 {product.name} 的目标用户而言，{benefits[0]}",
            *benefits[1:],
        ]
        if product.source_pages and pricing != "未公开":
            page = product.source_pages[0]
            evidence.append({
                "claim": pricing,
                "source_url": page.url,
                "source_excerpt": page.excerpt[:400],
            })
        products_result.append(
            {
                "slug": product.slug,
                "category": category,
                "what_it_sells": f"一款面向上述场景的{category}产品",
                "target_customers": customers,
                "problem_solved": f"用户缺少一种简单方式来完成这项任务：{scenario}",
                "plain_scenario": scenario,
                "benefits": benefits,
                "pricing_model": pricing,
                "conversion_path": conversion,
                "positioning": product.tagline or "定位未公开",
                "acquisition_hypothesis": "分析判断：通过 Product Hunt 首发获取早期用户",
                "differentiation": f"分析判断：以“{scenario}”这一具体入口区别于通用工具",
                "ai_role": ai_role,
                "maturity": "已在 Product Hunt 正式发布，实际采用仍待验证",
                "risks": "Product Hunt 热度不等于收入、留存或长期市场需求。",
                "confidence": "低" if not product.source_pages else "中",
                "fact_claims": evidence,
                "strategy_judgments": [
                    "通过新品发布社区测试定位和获取早期反馈"
                ],
            }
        )
    themes = [f"{name}（{count} 个产品）" for name, count in topic_counts.most_common(5)]
    customer_counts = Counter(
        value for item in products_result for value in item["target_customers"]
    )
    ai_core = sum("AI 是核心" in item["ai_role"] for item in products_result)
    result = {
        "analysis_version": ANALYSIS_VERSION,
        "available": True,
        "error": error or "使用规则分析；未调用 AI 模型",
        "key_judgments": [
            f"今日完整榜单共分析 {len(products)} 个产品，排名代表 Product Hunt 社区关注。",
            "多数新品仍处于获客和定位验证阶段，不能从首发热度推断商业成功。",
            f"{ai_core}/{len(products)} 个产品可确认 AI 是核心工作机制；"
            "其余产品不因上榜而被包装成 AI 产品。",
            f"出现较多的产品话题包括：{'、'.join(themes) or '资料不足'}。",
        ],
        "buying_capabilities": themes or ["资料积累后再判断"],
        "customer_patterns": [
            f"{name}（{count} 个产品）"
            for name, count in customer_counts.most_common(5)
        ],
        "business_model_patterns": ["免费入口、订阅和企业询价并存"],
        "new_product_forms": ["观察 AI 是否从附加功能变成产品核心工作流"],
        "products": products_result,
    }
    errors = product_analysis_quality_errors(result, len(products))
    if errors:
        result["available"] = False
        result["error"] += "；质量检查未通过：" + "、".join(errors)
    return result


def analyze_products(
    products: List[Product],
    client: Optional[OpenAIClient],
) -> Dict[str, Any]:
    if not client or not client.api_key:
        return _fallback_analysis(products, "免费 AI 凭证不可用，已使用规则分析")
    source = []
    for product in products:
        value = product.to_dict()
        value["source_pages"] = [
            {
                "url": page.url,
                "kind": page.kind,
                "excerpt": page.excerpt[:5_000],
            }
            for page in product.source_pages
        ]
        source.append(value)
    instructions = (
        "你是面向非程序员的产品与商业情报分析师。用简体中文逐项回答卖什么、卖给谁、"
        "解决什么、日常使用场景、实际好处、收费方式和成交入口。Product Hunt 字段与"
        "提供的官网原文属于可核实资料；事实主张必须在 fact_claims 中附 source_url 和"
        "逐字 source_excerpt。不能从资料确认的价格或客户写“未公开”。定位、获客、"
        "竞争差异等推断只能写入 strategy_judgments，并在正文使用“分析判断”措辞。"
        "不得把投票、排名推断为收入、留存或市场采用。说明 AI 是核心能力、辅助能力，"
        "还是没有足够证据。保持通俗但专业。products 必须与输入 slug 一一对应。"
    )
    try:
        batches = (
            [source[index : index + 3] for index in range(0, len(source), 3)]
            if client.provider == "github"
            else [source]
        )
        results = [
            client._structured_request(
                model=client.model,
                instructions=instructions,
                source=batch,
                schema=PRODUCT_SCHEMA,
                schema_name="product_hunt_business_analysis",
            )
            for batch in batches
        ]
        result = {
            "key_judgments": _unique(
                item for value in results for item in value["key_judgments"]
            )[:5],
            "buying_capabilities": _unique(
                item for value in results for item in value["buying_capabilities"]
            )[:8],
            "customer_patterns": _unique(
                item for value in results for item in value["customer_patterns"]
            )[:8],
            "business_model_patterns": _unique(
                item for value in results for item in value["business_model_patterns"]
            )[:8],
            "new_product_forms": _unique(
                item for value in results for item in value["new_product_forms"]
            )[:8],
            "products": [
                item for value in results for item in value["products"]
            ],
        }
        expected = {item.slug for item in products}
        actual = {str(item.get("slug", "")) for item in result["products"]}
        if expected != actual:
            raise ValueError("产品分析返回集合与输入不一致")
        result.update(
            {"analysis_version": ANALYSIS_VERSION, "available": True, "error": ""}
        )
        quality_errors = product_analysis_quality_errors(result, len(products))
        if quality_errors:
            raise ValueError("；".join(quality_errors))
        return result
    except Exception as exc:
        return _fallback_analysis(
            products, f"AI 分析失败，已使用规则分析：{type(exc).__name__}"
        )


def _unique(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text and text not in result:
            result.append(text)
    return result


def summarize_product_history(
    data_dir: Path, end_date: date, window_days: int
) -> Dict[str, Any]:
    start = end_date - timedelta(days=window_days - 1)
    snapshots = []
    for path in sorted(data_dir.glob("????-??-??.json")):
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
            item_date = date.fromisoformat(str(snapshot.get("date")))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if start <= item_date <= end_date and snapshot.get("products"):
            snapshots.append(snapshot)
    categories = Counter()
    pricing = Counter()
    customers = Counter()
    for snapshot in snapshots:
        for item in snapshot.get("analysis", {}).get("products", []):
            categories[str(item.get("category", "未分类"))] += 1
            pricing[str(item.get("pricing_model", "未公开"))] += 1
            customers.update(str(value) for value in item.get("target_customers", []))
    midpoint = len(snapshots) // 2
    earlier = snapshots[:midpoint]
    recent = snapshots[midpoint:]

    def category_rates(values: List[Dict[str, Any]]) -> Dict[str, float]:
        result: Counter[str] = Counter()
        for value in values:
            result.update(
                str(item.get("category", "未分类"))
                for item in value.get("analysis", {}).get("products", [])
            )
        days = max(1, len(values))
        return {name: count / days for name, count in result.items()}

    earlier_rates = category_rates(earlier)
    recent_rates = category_rates(recent)
    changes = sorted(
        (
            {
                "category": name,
                "change_per_day": round(
                    recent_rates.get(name, 0) - earlier_rates.get(name, 0), 2
                ),
            }
            for name in set(earlier_rates) | set(recent_rates)
        ),
        key=lambda item: item["change_per_day"],
        reverse=True,
    )
    return {
        "window_days": window_days,
        "observed_days": len(snapshots),
        "status": "complete" if len(snapshots) >= min(window_days, 5) else "observing",
        "top_categories": categories.most_common(6),
        "pricing_patterns": pricing.most_common(5),
        "customer_patterns": customers.most_common(5),
        "strengthening": [item for item in changes if item["change_per_day"] > 0][:5],
        "cooling": [item for item in reversed(changes) if item["change_per_day"] < 0][:5],
    }


def render_product_report(snapshot: Dict[str, Any]) -> str:
    analysis = snapshot["analysis"]
    product_map = {item["slug"]: item for item in analysis["products"]}
    lines = [
        f"# Product Hunt 商业情报 · {snapshot['date']}",
        "",
        "> 面向非程序员的产品与商业解读。排名代表 Product Hunt 社区关注，"
        "不等于收入、留存或市场采用。",
        "",
        "## 今日最重要的产品与商业判断",
        "",
    ]
    lines.extend(f"{index}. {value}" for index, value in enumerate(analysis["key_judgments"], 1))
    lines.extend(["", "## Top 15 产品卡片", ""])
    for product in snapshot["products"]:
        insight = product_map.get(product["slug"], {})
        lines.extend(
            [
                f"### {product['rank']}. [{product['name']}]({product['product_hunt_url']})",
                "",
                f"- **卖什么：** {insight.get('what_it_sells', '未公开')}",
                f"- **卖给谁：** {'、'.join(insight.get('target_customers', [])) or '未公开'}",
                f"- **解决什么：** {insight.get('problem_solved', '未公开')}",
                f"- **通俗场景：** {insight.get('plain_scenario', '未公开')}",
                f"- **有什么好处：** {'；'.join(insight.get('benefits', [])) or '未公开'}",
                f"- **怎么收费：** {insight.get('pricing_model', '未公开')}",
                f"- **怎么成交：** {insight.get('conversion_path', '未公开')}",
                f"- **AI 的作用：** {insight.get('ai_role', '未公开')}",
                f"- **成熟度与风险：** {insight.get('maturity', '未公开')}；"
                f"{insight.get('risks', '未公开')}",
                f"- **关注度：** 官方日榜第 {product['rank']}，"
                f"{product['votes_count']} 票、{product['comments_count']} 条评论",
                f"- **判断置信度：** {insight.get('confidence', '低')}",
                "",
            ]
        )
    for title, key in [
        ("今天大家在买什么能力", "buying_capabilities"),
        ("常见目标客户", "customer_patterns"),
        ("收费与销售模式", "business_model_patterns"),
        ("值得关注的新产品形态", "new_product_forms"),
    ]:
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {value}" for value in analysis.get(key, []))
    lines.extend(
        [
            "",
            "## 过去 7 天 / 30 天",
            "",
            f"- **7 天窗口：** 有效观察 {snapshot['trend_7d']['observed_days']}/7 天；"
            "正在增强："
            + "、".join(
                item["category"] for item in snapshot["trend_7d"].get("strengthening", [])
            )
            + "；可能降温："
            + "、".join(
                item["category"] for item in snapshot["trend_7d"].get("cooling", [])
            )
            + "。",
            f"- **30 天窗口：** 有效观察 {snapshot['trend_30d']['observed_days']}/30 天；"
            "正在增强："
            + "、".join(
                item["category"] for item in snapshot["trend_30d"].get("strengthening", [])
            )
            + "；可能降温："
            + "、".join(
                item["category"] for item in snapshot["trend_30d"].get("cooling", [])
            )
            + "。",
            "",
            "## 数据与证据限制",
            "",
            "- Product Hunt 排名是社区关注信号，不代表商业成功。",
            "- 官网明确内容标记为事实；定位、获客和竞争判断属于分析推断。",
            f"- 来源：[Product Hunt]({PRODUCT_HUNT_SOURCE})，仅用于个人或内部研究。",
            "",
        ]
    )
    return "\n".join(lines)


def producthunt_token() -> str:
    return re.sub(r"\s+", "", os.environ.get("PRODUCT_HUNT_TOKEN", ""))
