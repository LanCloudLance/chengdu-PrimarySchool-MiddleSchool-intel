import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from chengdu_edu_core.enums import (
    DistrictLevel,
    ParserStrategy,
    PolicyType,
    RecordType,
    SourceType,
)
from chengdu_edu_storage.orm import DataSource, District, EnrollmentPolicy, RawDocument, RecordVersion
from chengdu_edu_storage.repository import PolicyRepository


async def _seed_fixtures(db_session):
    district_id = uuid.uuid4()
    source_id = uuid.uuid4()
    raw_doc_id = uuid.uuid4()

    district = District(
        id=district_id,
        name="锦江区",
        code="jinjiang",
        level=DistrictLevel.CORE,
    )
    source = DataSource(
        id=source_id,
        name="test source",
        source_type=SourceType.GOV_WEBSITE,
        url="http://example.com",
        parser_strategy=ParserStrategy.RULE,
        schedule="daily",
        district_id=district_id,
    )
    raw_doc = RawDocument(
        id=raw_doc_id,
        source_id=source_id,
        content_hash="abc123",
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add_all([district, source, raw_doc])
    await db_session.commit()

    return district_id, raw_doc_id


@pytest.mark.asyncio
async def test_upsert_enrollment_creates_version_on_first_insert(db_session):
    district_id, raw_doc_id = await _seed_fixtures(db_session)
    repo = PolicyRepository(db_session)

    policy_id = await repo.upsert_enrollment(
        district_id=district_id,
        school_id=None,
        policy_type=PolicyType.GOV_POLICY,
        year=2026,
        fields={"enrollment_scope": "范围A"},
        source_doc_id=raw_doc_id,
        confidence=1.0,
    )

    policy = await db_session.get(EnrollmentPolicy, policy_id)
    assert policy.current_version == 1

    versions = (
        await db_session.execute(
            select(RecordVersion).where(
                RecordVersion.record_type == RecordType.ENROLLMENT,
                RecordVersion.record_id == policy_id,
            )
        )
    ).scalars().all()
    assert len(versions) == 1
    assert versions[0].version == 1

    history = await repo.get_field_changes(RecordType.ENROLLMENT, policy_id)
    assert history == []


@pytest.mark.asyncio
async def test_upsert_enrollment_creates_version_on_field_change(db_session):
    district_id, raw_doc_id = await _seed_fixtures(db_session)
    repo = PolicyRepository(db_session)

    policy_id = await repo.upsert_enrollment(
        district_id=district_id,
        school_id=None,
        policy_type=PolicyType.GOV_POLICY,
        year=2026,
        fields={"enrollment_scope": "范围A"},
        source_doc_id=raw_doc_id,
        confidence=1.0,
    )
    await repo.upsert_enrollment(
        district_id=district_id,
        school_id=None,
        policy_type=PolicyType.GOV_POLICY,
        year=2026,
        fields={"enrollment_scope": "范围B"},
        source_doc_id=raw_doc_id,
        confidence=1.0,
        existing_id=policy_id,
    )

    history = await repo.get_field_changes(RecordType.ENROLLMENT, policy_id)
    assert len(history) == 1
    assert history[0].field_path == "fields.enrollment_scope"
