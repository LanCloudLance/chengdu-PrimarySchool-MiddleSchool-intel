import uuid

import pytest

from chengdu_edu_core.enums import DistrictLevel, ParserStrategy, SourceType
from chengdu_edu_scheduler.pipeline import Pipeline
from chengdu_edu_scheduler.runner import SchedulerRunner
from chengdu_edu_storage.orm import DataSource, District
from chengdu_edu_storage.repository import PolicyRepository


@pytest.mark.asyncio
async def test_trigger_source_invokes_pipeline(db_session, mocker):
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
    db_session.add_all([district, source])
    await db_session.commit()

    mock_run = mocker.patch(
        "chengdu_edu_scheduler.runner.Pipeline.run_source",
        new=mocker.AsyncMock(),
    )

    repo = PolicyRepository(db_session)
    pipeline = Pipeline(repo)
    runner = SchedulerRunner(pipeline, [source])
    await runner.trigger("source", source_id)

    mock_run.assert_awaited_once_with(source)


@pytest.mark.asyncio
async def test_trigger_all_invokes_each_active_source(db_session, mocker):
    district_id = uuid.uuid4()
    sources = [
        DataSource(
            id=uuid.uuid4(),
            name=f"source-{index}",
            source_type=SourceType.GOV_WEBSITE,
            url=f"https://example.com/{index}",
            parser_strategy=ParserStrategy.RULE,
            schedule="0 0 1 * *",
            district_id=district_id,
            is_active=True,
        )
        for index in range(2)
    ]
    district = District(
        id=district_id,
        name="锦江区",
        code="jinjiang",
        level=DistrictLevel.CORE,
    )
    db_session.add(district)
    db_session.add_all(sources)
    await db_session.commit()

    mock_run = mocker.patch(
        "chengdu_edu_scheduler.runner.Pipeline.run_source",
        new=mocker.AsyncMock(),
    )

    repo = PolicyRepository(db_session)
    pipeline = Pipeline(repo)
    runner = SchedulerRunner(pipeline, sources)
    await runner.trigger("all")

    assert mock_run.await_count == 2
