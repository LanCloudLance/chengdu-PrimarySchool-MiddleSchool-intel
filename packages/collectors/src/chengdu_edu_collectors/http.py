import asyncio

import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from chengdu_edu_core.hashing import content_hash
from chengdu_edu_core.models import RawDocument


class HttpCollector:
    source_type = "gov_website"

    async def collect(self, source) -> RawDocument:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            for attempt in range(3):
                try:
                    resp = await client.get(source.url)
                    resp.raise_for_status()
                    text = self._extract_text(resp.text)
                    return RawDocument(
                        source_id=source.id,
                        content_hash=content_hash(text),
                        raw_content=text,
                        fetched_at=datetime.now(timezone.utc),
                        http_status=resp.status_code,
                    )
                except httpx.HTTPError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2**attempt)

    def _extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)
