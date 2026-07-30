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
ANALYSIS_VERSION = 1

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
        pricing = "未公开"
        conversion = "访问官网了解或开始使用"
        excerpt = " ".join(page.excerpt.lower() for page in product.source_pages)
        if any(word in excerpt for word in ["free trial", "start free", "try for free"]):
            pricing = "提供免费试用或免费入口（以官网为准）"
            conversion = "自助试用"
        elif any(word in excerpt for word in ["contact sales", "book a demo"]):
            pricing = "企业询价"
            conversion = "预约演示或联系销售"
        elif any(word in excerpt for word in ["pricing", "per month", "/month"]):
            pricing = "官网提供付费方案，具体价格需人工核对"
            conversion = "官网自助购买"
        products_result.append(
            {
                "slug": product.slug,
                "category": product.topics[0] if product.topics else "数字产品",
                "what_it_sells": product.tagline or product.description or "未公开",
                "target_customers": ["目标客户未公开"],
                "problem_solved": product.description or product.tagline or "未公开",
                "plain_scenario": "可从产品官网进一步确认具体使用场景。",
                "benefits": ["产品方尚未提供足够资料，需进一步核实"],
                "pricing_model": pricing,
                "conversion_path": conversion,
                "positioning": product.tagline or "定位未公开",
                "acquisition_hypothesis": "分析判断：通过 Product Hunt 首发获取早期用户",
                "differentiation": "差异尚待与竞品核对",
                "ai_role": (
                    "可能与 AI 直接相关，需核实具体作用"
                    if any(
                        value in (" ".join(product.topics) + product.tagline).lower()
                        for value in ["ai", "agent", "gpt", "llm"]
                    )
                    else "未发现足够证据说明 AI 是核心能力"
                ),
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
    return {
        "analysis_version": ANALYSIS_VERSION,
        "available": True,
        "error": error or "使用规则分析；未调用 AI 模型",
        "key_judgments": [
            f"今日完整榜单共分析 {len(products)} 个产品，排名代表 Product Hunt 社区关注。",
            "多数新品仍处于获客和定位验证阶段，不能从首发热度推断商业成功。",
            f"出现较多的产品话题包括：{'、'.join(themes) or '资料不足'}。",
        ],
        "buying_capabilities": themes or ["资料积累后再判断"],
        "customer_patterns": ["目标客户需要结合官网资料逐项核实"],
        "business_model_patterns": ["免费入口、订阅和企业询价并存"],
        "new_product_forms": ["观察 AI 是否从附加功能变成产品核心工作流"],
        "products": products_result,
    }


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
    return {
        "window_days": window_days,
        "observed_days": len(snapshots),
        "status": "complete" if len(snapshots) >= min(window_days, 5) else "observing",
        "top_categories": categories.most_common(6),
        "pricing_patterns": pricing.most_common(5),
        "customer_patterns": customers.most_common(5),
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
            f"- 7 天窗口：有效观察 {snapshot['trend_7d']['observed_days']}/7 天。",
            f"- 30 天窗口：有效观察 {snapshot['trend_30d']['observed_days']}/30 天。",
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
