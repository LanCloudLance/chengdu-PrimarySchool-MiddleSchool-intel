import uuid
from datetime import datetime, timezone

import pytest

from chengdu_edu_core.enums import (
    DistrictLevel,
    JobStatus,
    ParserStrategy,
    SourceType,
)
from chengdu_edu_core.models import RawDocument
from chengdu_edu_scheduler.pipeline import Pipeline
from chengdu_edu_storage.orm import DataSource, District, RawDocument as RawDocumentORM
from chengdu_edu_storage.repository import PolicyRepository

CONTENT_HASH = "a" * 64


@pytest.mark.asyncio
async def test_pipeline_skips_unchanged_hash(db_session, mocker):
    district_id = uuid.uuid4()
    source_id = uuid.uuid4()

    district = District(
        id=district_id,
        name="锦江区",
        code="jinjiang",
        level=DistrictLevel.CORE,
    )
    source = DataSource(
        id=source_id,
        name="锦江区教育局-招生政策",
        source_type=SourceType.GOV_WEBSITE,
        url="https://www.cdjx.gov.cn/",
        parser_strategy=ParserStrategy.RULE,
        schedule="0 0 1 * *",
        district_id=district_id,
        is_active=True,
    )
    previous_doc = RawDocumentORM(
        source_id=source_id,
        content_hash=CONTENT_HASH,
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add_all([district, source, previous_doc])
    await db_session.commit()

    mock_raw = RawDocument(
        source_id=source_id,
        content_hash=CONTENT_HASH,
        raw_content="unchanged content",
        fetched_at=datetime.now(timezone.utc),
    )
    mock_collector = mocker.Mock()
    mock_collector.collect = mocker.AsyncMock(return_value=mock_raw)
    mocker.patch(
        "chengdu_edu_scheduler.pipeline.get_collector",
        return_value=mock_collector,
    )
    mock_parser = mocker.Mock()
    mock_parser.parse = mocker.AsyncMock()
    mocker.patch(
        "chengdu_edu_scheduler.pipeline.get_parser",
        return_value=mock_parser,
    )

    repo = PolicyRepository(db_session)
    pipeline = Pipeline(repo)
    job_run = await pipeline.run_source(source)

    assert job_run.status == JobStatus.SKIPPED
    assert job_run.docs_fetched == 0
    assert job_run.changes_detected == 0
    assert job_run.error_message is None
    assert job_run.finished_at is not None
    mock_collector.collect.assert_awaited_once_with(source)
    mock_parser.parse.assert_not_called()
