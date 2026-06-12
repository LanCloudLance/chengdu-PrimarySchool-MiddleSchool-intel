"""武侯区学校 URL 校验与 alternate 解析（verify / verify_data 共用）。"""
from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=12.0, write=5.0, pool=5.0)


def is_website_ok(status: int | None, content_length: int) -> bool:
    if status is None:
        return False
    if status < 400 and content_length > 100:
        return True
    if status in (403, 520) and content_length > 500:
        return True
    return False


def alternate_scheme(url: str) -> str | None:
    if url.startswith("http://"):
        return "https://" + url[7:]
    if url.startswith("https://"):
        return "http://" + url[8:]
    return None


def normalize_alternate(entry: str | dict) -> dict:
    if isinstance(entry, str):
        return {"url": entry, "source": "mirror"}
    return entry


def collect_alternate_urls(
    *,
    primary: str | None,
    school_name: str,
    enrichment: dict,
) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()

    def add(entry: str | dict) -> None:
        row = normalize_alternate(entry)
        url = row.get("url")
        if not url or url in seen:
            return
        seen.add(url)
        out.append(row)

    for entry in enrichment.get("alternate_by_name", {}).get(school_name, []):
        add(entry)
    if primary:
        for entry in enrichment.get("alternate_urls", {}).get(primary, []):
            add(entry)
    fallback = enrichment.get("primary_mirrors", {}).get(primary)
    if fallback:
        add({"url": fallback, "source": "bendibao"})
    return out


def build_verify_chain(
    *,
    primary: str,
    school_name: str,
    enrichment: dict,
) -> list[str]:
    """验证时优先校名 mirror；有校名映射时不串用同主域其他校 mirror。"""
    by_name = enrichment.get("alternate_by_name", {}).get(school_name, [])
    if by_name:
        return [primary] + [normalize_alternate(e)["url"] for e in by_name]
    return [primary] + [
        row["url"] for row in collect_alternate_urls(
            primary=primary, school_name=school_name, enrichment=enrichment
        )
    ]


def mirror_bendibao_variants(url: str) -> list[str]:
    """本地宝 wangdian 详情页变体（mobile 优先）。"""
    if "bendibao.com" not in url or "wangdian" not in url:
        return [url]
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    ordered: list[str] = []
    for scheme in ("https", "http"):
        for prefix in ("m.cd.", "cd."):
            candidate = f"{scheme}://{prefix}bendibao.com{path}"
            if candidate not in ordered:
                ordered.append(candidate)
    if url not in ordered:
        ordered.append(url)
    return ordered


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return match.group(1).strip() if match else ""


def _name_in_page(school_name: str, text: str, *, list_page: bool = False) -> bool:
    cleaned = school_name.replace("成都市", "").replace("成都", "").replace("四川", "")
    if cleaned and cleaned in text:
        return True
    if list_page:
        return bool(cleaned) and cleaned in text
    for token in (cleaned[:6], cleaned[:4], cleaned[-4:]):
        if len(token) >= 3 and token in text:
            return True
    for keyword in ("附属", "实验", "外国语", "龙江路", "玉林", "石室", "棕北"):
        if keyword in cleaned and keyword in text:
            return True
    return False


def _mirror_name_ok(school_name: str, html: str) -> bool:
    title = _extract_title(html)
    body = html
    if title and _name_in_page(school_name, title):
        return True
    if _name_in_page(school_name, body):
        return True
    cleaned = school_name.replace("成都市", "").replace("成都", "").replace("四川", "")
    if title and cleaned and cleaned[:4] in title and "地址" in title:
        return True
    return False


async def check_url(
    client: httpx.AsyncClient,
    url: str,
    *,
    school_name: str | None = None,
    require_name_match: bool = True,
    mirror_only: bool = False,
) -> dict:
    candidates = mirror_bendibao_variants(url) if mirror_only else [url]
    if not mirror_only:
        alt = alternate_scheme(url)
        if alt and "bendibao.com" not in url:
            candidates.append(alt)
    last: dict[str, Any] = {"url": url, "ok": False}
    for candidate in candidates:
        for attempt in range(2):
            try:
                resp = await client.get(candidate, follow_redirects=True)
                text = resp.text
                ok = is_website_ok(resp.status_code, len(resp.content))
                if ok and require_name_match and school_name and "bendibao.com" in candidate:
                    list_page = "xiaoxuelist" in candidate or "chuzhonglist" in candidate
                    if mirror_only:
                        ok = _mirror_name_ok(school_name, text)
                    elif not _name_in_page(school_name, text, list_page=list_page):
                        ok = False
                if ok and "拼图验证" in text:
                    ok = False
                last = {
                    "url": candidate,
                    "http_status": resp.status_code,
                    "ok": ok,
                    "content_length": len(resp.content),
                    "attempt": attempt + 1,
                }
                if ok:
                    return last
                if resp.status_code not in (502, 503, 504):
                    break
            except httpx.HTTPError as exc:
                last = {"url": candidate, "ok": False, "error": str(exc)}
                break
            await asyncio.sleep(0.8)
    return last


async def verify_school_website(
    client: httpx.AsyncClient,
    *,
    primary: str,
    school_name: str,
    enrichment: dict,
) -> dict:
    """依次尝试 primary 与 alternate_urls，返回最优结果。"""
    chain = build_verify_chain(
        primary=primary, school_name=school_name, enrichment=enrichment
    )
    last: dict[str, Any] = {"url": primary, "ok": False, "via": "primary"}
    for url in chain:
        is_primary = url == primary
        result = await check_url(
            client,
            url,
            school_name=school_name,
            require_name_match=is_primary,
        )
        result["via"] = "primary" if is_primary else "alternate"
        last = result
        if result.get("ok"):
            return result
    return last


async def verify_mirror_only(
    client: httpx.AsyncClient,
    *,
    school_name: str,
    enrichment: dict,
) -> dict:
    """无独立官网时，仅校验本地宝 mirror 页是否含校名且可达。"""
    alternates = collect_alternate_urls(
        primary=None, school_name=school_name, enrichment=enrichment
    )
    if not alternates:
        return {"url": None, "ok": False, "via": "mirror_only"}
    last: dict[str, Any] = {
        "url": alternates[0]["url"],
        "ok": False,
        "via": "mirror_only",
    }
    for row in alternates:
        url = row["url"]
        result = await check_url(
            client,
            url,
            school_name=school_name,
            require_name_match=True,
            mirror_only=True,
        )
        result["via"] = "mirror_only"
        last = result
        if result.get("ok"):
            return result
    return last
