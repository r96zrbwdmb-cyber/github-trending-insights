from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin

from .models import Repository


def parse_count(value: str) -> int:
    text = value.strip().lower().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([km]?)", text)
    if not match:
        return 0
    number = float(match.group(1))
    multiplier = {"": 1, "k": 1_000, "m": 1_000_000}[match.group(2)]
    return int(number * multiplier)


class TrendingHTMLParser(HTMLParser):
    """Small, isolated parser for GitHub's Trending repository cards."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.repositories: List[Repository] = []
        self.current: Optional[Dict[str, object]] = None
        self.article_depth = 0
        self.capture = ""
        self.capture_depth = 0
        self.link_kind = ""
        self.buffers: Dict[str, List[str]] = {}

    def handle_starttag(self, tag: str, attrs: List[tuple]) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "article" and "Box-row" in classes:
            self.current = {}
            self.article_depth = 1
            self.buffers = {}
            return
        if self.current is None:
            return
        if tag == "article":
            self.article_depth += 1
        if tag == "h2":
            self._start_capture("heading")
        elif tag == "p" and ("col-9" in classes or "color-fg-muted" in classes):
            self._start_capture("description")
        elif attributes.get("itemprop") == "programmingLanguage":
            self._start_capture("language")
        elif tag == "a":
            href = attributes.get("href", "")
            if "/stargazers" in href:
                self.link_kind = "stars"
                self._start_capture("stars")
            elif "/forks" in href or "/network/members" in href:
                self.link_kind = "forks"
                self._start_capture("forks")
            elif self.capture == "heading" and re.match(r"^/[^/]+/[^/]+/?$", href):
                self.current["href"] = href
        elif tag == "span" and "float-sm-right" in classes:
            self._start_capture("stars_today")
        if self.capture:
            self.capture_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.current is None:
            return
        if self.capture:
            self.capture_depth -= 1
            if self.capture_depth <= 0:
                self.capture = ""
                self.link_kind = ""
        if tag == "article":
            self.article_depth -= 1
            if self.article_depth == 0:
                self._finish_repository()

    def handle_data(self, data: str) -> None:
        if self.current is not None and self.capture:
            self.buffers.setdefault(self.capture, []).append(data)

    def _start_capture(self, name: str) -> None:
        self.capture = name
        self.capture_depth = 0
        self.buffers.setdefault(name, [])

    def _text(self, name: str) -> str:
        return " ".join(" ".join(self.buffers.get(name, [])).split())

    def _finish_repository(self) -> None:
        assert self.current is not None
        href = str(self.current.get("href", "")).rstrip("/")
        heading = self._text("heading").replace(" / ", "/").replace(" ", "")
        full_name = href.strip("/") if href else heading.strip("/")
        if re.match(r"^[^/]+/[^/]+$", full_name):
            self.repositories.append(
                Repository(
                    rank=len(self.repositories) + 1,
                    full_name=full_name,
                    url=urljoin("https://github.com", f"/{full_name}"),
                    description=self._text("description"),
                    language=self._text("language"),
                    stars=parse_count(self._text("stars")),
                    forks=parse_count(self._text("forks")),
                    stars_today=parse_count(self._text("stars_today")),
                )
            )
        self.current = None
        self.capture = ""
        self.capture_depth = 0
        self.buffers = {}


def parse_trending_html(html: str, limit: int = 25) -> List[Repository]:
    parser = TrendingHTMLParser()
    parser.feed(html)
    repositories = parser.repositories[:limit]
    if not repositories:
        raise ValueError(
            "GitHub Trending 页面中没有找到仓库卡片，页面结构可能已变化"
        )
    names = [repo.full_name for repo in repositories]
    if len(names) != len(set(names)):
        raise ValueError("GitHub Trending 解析结果包含重复仓库")
    return repositories
