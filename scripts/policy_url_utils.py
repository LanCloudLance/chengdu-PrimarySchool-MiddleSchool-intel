"""政策页 URL 变体与可达性探测（verify_data / discover / collector 共用）。"""
from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

POLICY_YEAR = 2026
SCOPE_RE = re.compile(
    r"(?:公办小学入学对象|本区户籍适龄儿童|新区户籍适龄儿童|金牛区户籍适龄儿童)"
)
TIME_RE = re.compile(r"5月6日[—\-~至]+12日|5月6日10[：:]00")

DISTRICT_KEYWORDS: dict[str, list[str]] = {
    "jinjiang": ["锦江区"],
    "qingyang": ["青羊区"],
    "wuhou": ["武侯区"],
    "chenghua": ["成华区", "成华"],
    "jinniu": ["金牛区"],
    "gaoxin": ["高新区", "成都高新区"],
    "tianfu": ["天府新区", "四川天府新区"],
}

# 由 discover 脚本探测维护；首轮含已知可达的 news.chengdu.cn 镜像
NEWS_CANDIDATE_POOL: list[str] = [
    "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "https://news.chengdu.cn/2026/0316/69b7fb793a56c94052c41bec.shtml",
    "https://news.chengdu.cn/2026/0331/69cb82823a56c94052c6e9c4.shtml",
]

# 各区首选 news.chengdu.cn 政策镜像（登记点页见 registration_url，不作为 policy fallback）
DISTRICT_NEWS_FALLBACK: dict[str, str] = {
    "jinjiang": "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "qingyang": "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "wuhou": "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "chenghua": "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "gaoxin": "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "tianfu": "https://news.chengdu.cn/2026/0331/69cb82823a56c94052c6e9c4.shtml",
}


def is_registration_bendibao(url: str) -> bool:
    """本地宝 2026424 系列多为登记点一览，不是政策正文。"""
    return "bendibao.com" in url and "/2026424/" in url


def is_news_policy_url(url: str) -> bool:
    return "news.chengdu.cn" in url


def page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


def check_policy_page(text: str, expected_year: int = POLICY_YEAR) -> dict[str, Any]:
    blocked = "拼图验证" in text or len(text) < 200
    has_year = str(expected_year) in text
    return {
        "blocked": blocked,
        "has_year": has_year,
        "has_scope": bool(SCOPE_RE.search(text)),
        "has_registration_time": bool(TIME_RE.search(text)),
        "content_length": len(text),
        "ok": not blocked and has_year and len(text) > 500,
    }


def bendibao_variants(url: str) -> list[str]:
    if "bendibao.com" not in url:
        return [url]
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    path = parsed.path
    if parsed.query:
        path = f"{path}?{parsed.query}"
    bases = []
    for scheme in ("https", "http"):
        for prefix in ("cd.", "m.cd.", "www.cd."):
            bases.append(f"{scheme}://{prefix}bendibao.com{path}")
    seen: list[str] = []
    for item in [url, *bases]:
        if item not in seen:
            seen.append(item)
    return seen


def score_candidate(text: str, district_code: str | None) -> int:
    check = check_policy_page(text)
    if not check["ok"]:
        return -1
    score = 10
    if check["has_scope"]:
        score += 5
    if check["has_registration_time"]:
        score += 3
    if district_code:
        for kw in DISTRICT_KEYWORDS.get(district_code, []):
            if kw in text:
                score += 8
                break
    score += min(len(text) // 2000, 5)
    return score


async def probe_url(
    client: httpx.AsyncClient,
    url: str,
    *,
    district_code: str | None = None,
) -> dict[str, Any]:
    try:
        resp = await client.get(url, follow_redirects=True)
        text = page_text(resp.text)
        check = check_policy_page(text)
        return {
            "url": str(resp.url),
            "http_status": resp.status_code,
            "score": score_candidate(text, district_code),
            "error": None,
            **check,
        }
    except httpx.HTTPError as exc:
        return {
            "url": url,
            "http_status": None,
            "score": -1,
            "ok": False,
            "blocked": False,
            "error": str(exc),
        }


async def find_best_policy_url(
    candidates: list[str],
    *,
    district_code: str | None = None,
    max_probes: int = 12,
) -> dict[str, Any] | None:
    seen: set[str] = set()
    ordered: list[str] = []
    for url in candidates:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    best: dict[str, Any] | None = None
    async with httpx.AsyncClient(timeout=25.0, headers=HEADERS, follow_redirects=True) as client:
        for index, url in enumerate(ordered[:max_probes]):
            if index > 0:
                await asyncio.sleep(1.5)
            row = await probe_url(client, url, district_code=district_code)
            if row.get("ok") and (best is None or row["score"] > best["score"]):
                best = row
    return best
