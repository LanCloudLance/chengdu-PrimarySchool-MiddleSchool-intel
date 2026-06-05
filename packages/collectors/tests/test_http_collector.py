from types import SimpleNamespace
from uuid import uuid4

import pytest

from chengdu_edu_collectors.http import HttpCollector


@pytest.mark.asyncio
async def test_http_collector_fetches_and_hashes(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/policy",
        text="<html>招生范围：A区</html>",
    )
    collector = HttpCollector()
    source = SimpleNamespace(
        id=uuid4(),
        url="https://example.com/policy",
        source_type="gov_website",
    )
    doc = await collector.collect(source)
    assert "招生范围" in doc.raw_content
    assert len(doc.content_hash) == 64
    assert doc.http_status == 200
