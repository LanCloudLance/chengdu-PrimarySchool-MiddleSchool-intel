import asyncio

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from chengdu_edu_core.hashing import content_hash
from chengdu_edu_core.models import RawDocument


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

MIN_CONTENT_LENGTH = 400

NEWS_CANDIDATE_POOL = [
    "https://news.chengdu.cn/2026/0312/69b28243f34d440475d454d6.shtml",
    "https://news.chengdu.cn/2026/0316/69b7fb793a56c94052c41bec.shtml",
    "https://news.chengdu.cn/2026/0331/69cb82823a56c94052c6e9c4.shtml",
]


def _bendibao_variants(url: str) -> list[str]:
    if "bendibao.com" not in url:
        return [url]
    from urllib.parse import urlparse

    parsed = urlparse(url)
    path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    out = [url]
    for scheme in ("https", "http"):
        for prefix in ("cd.", "m.cd.", "www.cd."):
            candidate = f"{scheme}://{prefix}bendibao.com{path}"
            if candidate not in out:
                out.append(candidate)
    return out


class HttpCollector:
    source_type = "gov_website"

    async def collect(self, source) -> RawDocument:
        meta = getattr(source, "metadata_", None) or {}
        urls = [source.url]
        if isinstance(meta, dict):
            fallback = meta.get("fallback_url")
            if fallback and fallback not in urls:
                urls.append(fallback)
            reg = meta.get("registration_url")
            if reg and reg not in urls:
                urls.append(reg)

        try:
            from policy_url_utils import NEWS_CANDIDATE_POOL as SCRIPT_NEWS_POOL
            from policy_url_utils import bendibao_variants
        except ImportError:
            bendibao_variants = _bendibao_variants
            SCRIPT_NEWS_POOL = NEWS_CANDIDATE_POOL

        expanded: list[str] = []
        for url in urls:
            if "bendibao.com" in url:
                expanded.extend(bendibao_variants(url))
            else:
                expanded.append(url)
        for news_url in SCRIPT_NEWS_POOL:
            if news_url not in expanded:
                expanded.append(news_url)
        urls = expanded

        async with httpx.AsyncClient(
            timeout=30.0, follow_redirects=True, headers=DEFAULT_HEADERS
        ) as client:
            last_blocked: str | None = None
            for url in urls:
                for attempt in range(5):
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        if "challenge" in str(resp.url):
                            last_blocked = str(resp.url)
                            await asyncio.sleep(min(8 * (2**attempt), 60))
                            continue
                        text = self._extract_text(resp.text)
                        if self._is_blocked(resp.text, text, url):
                            last_blocked = url
                            await asyncio.sleep(min(8 * (2**attempt), 60))
                            continue
                        return RawDocument(
                            source_id=source.id,
                            content_hash=content_hash(text),
                            raw_content=text,
                            fetched_at=datetime.now(timezone.utc),
                            http_status=resp.status_code,
                        )
                    except httpx.HTTPError:
                        if attempt == 4:
                            raise
                        await asyncio.sleep(2**attempt)

            raise RuntimeError(
                f"blocked or empty content from {source.url}"
                + (f" (fallback also blocked: {last_blocked})" if last_blocked else "")
            )

    def _is_blocked(self, html: str, text: str, url: str) -> bool:
        if "拼图验证" in text or "请完成拼图验证" in text:
            return True
        if "challenge" in html and "bendibao" in url:
            return True
        if "bendibao" in url and len(text) < MIN_CONTENT_LENGTH:
            return True
        return False

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
