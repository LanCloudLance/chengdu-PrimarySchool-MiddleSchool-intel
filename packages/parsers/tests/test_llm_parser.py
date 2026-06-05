import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from chengdu_edu_core.models import RawDocument
from chengdu_edu_parsers.llm_parser import LLMParser


class FakeCompletion:
    def __init__(self, data: dict) -> None:
        self.choices = [
            SimpleNamespace(message=SimpleNamespace(content=json.dumps(data)))
        ]


@pytest.fixture
def raw_doc() -> RawDocument:
    return RawDocument(
        source_id=uuid4(),
        content_hash="abc123",
        raw_content="2026年锦江区小学招生范围：南门片区，报名时间 2026-03-01 ~ 2026-03-15",
        fetched_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def source() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), source_type="private_website")


@pytest.mark.asyncio
async def test_llm_parser_returns_structured_fields(mocker, raw_doc, source):
    mock_client = mocker.patch("chengdu_edu_parsers.llm_parser.AsyncOpenAI")
    mock_client.return_value.chat.completions.create = AsyncMock(
        return_value=FakeCompletion(
            {
                "enrollment_scope": "南门片区",
                "registration_time": "2026-03-01 ~ 2026-03-15",
                "confidence": 0.92,
            }
        )
    )
    parser = LLMParser(api_key="test", base_url="http://test", model="test")
    result = await parser.parse(raw_doc, source)
    assert result.fields["enrollment_scope"] == "南门片区"
    assert result.confidence == 0.92
    assert result.needs_review is False


@pytest.mark.asyncio
async def test_llm_parser_marks_low_confidence_for_review(mocker, raw_doc, source):
    mock_client = mocker.patch("chengdu_edu_parsers.llm_parser.AsyncOpenAI")
    mock_client.return_value.chat.completions.create = AsyncMock(
        return_value=FakeCompletion(
            {
                "enrollment_scope": "未知",
                "registration_time": "",
                "confidence": 0.5,
            }
        )
    )
    parser = LLMParser(api_key="test", base_url="http://test", model="test")
    result = await parser.parse(raw_doc, source)
    assert result.confidence == 0.5
    assert result.needs_review is True
