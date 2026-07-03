import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from chengdu_edu_core.enums import PolicyType, RecordType
from chengdu_edu_api.mapping_display import mapping_status_badge
from chengdu_edu_storage.orm import (
    District,
    EnrollmentPolicy,
    FieldChange,
    RecordVersion,
    School,
)


async def _school_id(db_session, name: str):
    return (
        await db_session.execute(select(School.id).where(School.name == name))
    ).scalar_one()


async def _district_id(db_session, code: str):
    return (
        await db_session.execute(select(District.id).where(District.code == code))
    ).scalar_one()


@pytest.mark.asyncio
async def test_mapping_review_defaults_to_needs_review(app, db_session, seeded_data):
    jinjiang_id = await _district_id(db_session, "jinjiang")
    pending_school_id = await _school_id(db_session, "锦江第一小学")
    verified_school_id = await _school_id(db_session, "成都七中实验学校")
    db_session.add_all(
        [
            EnrollmentPolicy(
                id=uuid.uuid4(),
                district_id=jinjiang_id,
                school_id=pending_school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=2026,
                fields={
                    "enrollment_scope": "东大街以北、静安路以南片区",
                    "mapping_status": "pending_review",
                    "source_page": "http://example.com/ocr",
                },
                current_version=1,
            ),
            EnrollmentPolicy(
                id=uuid.uuid4(),
                district_id=jinjiang_id,
                school_id=verified_school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=2026,
                fields={
                    "enrollment_scope": "水井坊街道片区",
                    "mapping_status": "verified",
                },
                current_version=1,
            ),
        ]
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/review/mappings")

    assert resp.status_code == 200
    assert "锦江第一小学" in resp.text
    assert "待复核" in resp.text
    assert "/review/mappings.csv?" in resp.text
    assert "成都七中实验学校" not in resp.text


@pytest.mark.asyncio
async def test_mapping_review_can_filter_verified(app, db_session, seeded_data):
    jinjiang_id = await _district_id(db_session, "jinjiang")
    verified_school_id = await _school_id(db_session, "成都七中实验学校")
    db_session.add(
        EnrollmentPolicy(
            id=uuid.uuid4(),
            district_id=jinjiang_id,
            school_id=verified_school_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2026,
            fields={
                "enrollment_scope": "水井坊街道片区",
                "mapping_status": "verified",
            },
            current_version=1,
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/review/mappings", params={"status": "verified"})

    assert resp.status_code == 200
    assert "成都七中实验学校" in resp.text
    assert "已核实" in resp.text


def test_pending_review_badge_is_first_class_status():
    badge = mapping_status_badge("pending_review")

    assert badge is not None
    assert badge["label"] == "待复核"
    assert "purple" in badge["badge_class"]


@pytest.mark.asyncio
async def test_mapping_review_csv_exports_filtered_review_rows(
    app, db_session, seeded_data
):
    jinjiang_id = await _district_id(db_session, "jinjiang")
    pending_school_id = await _school_id(db_session, "锦江第一小学")
    verified_school_id = await _school_id(db_session, "成都七中实验学校")
    db_session.add_all(
        [
            EnrollmentPolicy(
                id=uuid.uuid4(),
                district_id=jinjiang_id,
                school_id=pending_school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=2026,
                fields={
                    "enrollment_scope": "东大街以北、静安路以南片区",
                    "mapping_status": "pending_review",
                    "source_page": "http://example.com/ocr",
                },
                current_version=1,
            ),
            EnrollmentPolicy(
                id=uuid.uuid4(),
                district_id=jinjiang_id,
                school_id=verified_school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=2026,
                fields={
                    "enrollment_scope": "水井坊街道片区",
                    "mapping_status": "verified",
                },
                current_version=1,
            ),
        ]
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/review/mappings.csv",
            params={"status": "pending_review", "year": 2026},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "review_decision" in resp.text
    assert "锦江第一小学" in resp.text
    assert "pending_review" in resp.text
    assert "成都七中实验学校" not in resp.text


@pytest.mark.asyncio
async def test_mapping_review_page_defaults_to_read_only(
    app, db_session, seeded_data, monkeypatch
):
    monkeypatch.delenv("ENABLE_REVIEW_WRITE", raising=False)
    monkeypatch.delenv("REVIEW_WRITE_TOKEN", raising=False)
    jinjiang_id = await _district_id(db_session, "jinjiang")
    pending_school_id = await _school_id(db_session, "锦江第一小学")
    policy_id = uuid.uuid4()
    db_session.add(
        EnrollmentPolicy(
            id=policy_id,
            district_id=jinjiang_id,
            school_id=pending_school_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2026,
            fields={
                "enrollment_scope": "东大街以北、静安路以南片区",
                "mapping_status": "pending_review",
            },
            current_version=1,
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/review/mappings")
        post = await client.post(
            f"/review/mappings/{policy_id}/decision",
            data={
                "year": "2026",
                "district": "jinjiang",
                "status": "pending_review",
                "current_status": "pending_review",
                "review_decision": "verified",
            },
        )

    assert page.status_code == 200
    assert "复核写入未开启" in page.text
    assert f"/review/mappings/{policy_id}/decision" not in page.text
    assert post.status_code == 403


@pytest.mark.asyncio
async def test_mapping_review_decision_post_updates_policy_and_audit_rows(
    app, db_session, seeded_data, monkeypatch
):
    monkeypatch.setenv("ENABLE_REVIEW_WRITE", "true")
    jinjiang_id = await _district_id(db_session, "jinjiang")
    pending_school_id = await _school_id(db_session, "锦江第一小学")
    policy_id = uuid.uuid4()
    db_session.add(
        EnrollmentPolicy(
            id=policy_id,
            district_id=jinjiang_id,
            school_id=pending_school_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2026,
            fields={
                "enrollment_scope": "东大街以北、静安路以南片区",
                "mapping_status": "pending_review",
            },
            current_version=1,
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/review/mappings/{policy_id}/decision",
            data={
                "year": "2026",
                "district": "jinjiang",
                "status": "pending_review",
                "current_status": "pending_review",
                "review_decision": "verified",
                "review_notes": "网页复核通过",
                "reviewed_by": "tester",
            },
            follow_redirects=False,
        )

    assert resp.status_code == 303
    assert "message=updated" in resp.headers["location"]
    policy = await db_session.get(EnrollmentPolicy, policy_id)
    assert policy.fields["mapping_status"] == "verified"
    assert policy.fields["previous_mapping_status"] == "pending_review"
    assert policy.fields["review_notes"] == "网页复核通过"
    assert policy.fields["reviewed_by"] == "tester"
    assert policy.fields["review_source"] == "mapping_review_web"
    assert policy.current_version == 2

    versions = (
        await db_session.execute(
            select(RecordVersion).where(
                RecordVersion.record_type == RecordType.ENROLLMENT,
                RecordVersion.record_id == policy_id,
            )
        )
    ).scalars().all()
    assert len(versions) == 1
    changes = (
        await db_session.execute(
            select(FieldChange).where(
                FieldChange.record_type == RecordType.ENROLLMENT,
                FieldChange.record_id == policy_id,
            )
        )
    ).scalars().all()
    assert "fields.mapping_status" in {change.field_path for change in changes}


@pytest.mark.asyncio
async def test_mapping_review_decision_post_rejects_stale_status(
    app, db_session, seeded_data, monkeypatch
):
    monkeypatch.setenv("ENABLE_REVIEW_WRITE", "true")
    jinjiang_id = await _district_id(db_session, "jinjiang")
    pending_school_id = await _school_id(db_session, "锦江第一小学")
    policy_id = uuid.uuid4()
    db_session.add(
        EnrollmentPolicy(
            id=policy_id,
            district_id=jinjiang_id,
            school_id=pending_school_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2026,
            fields={
                "enrollment_scope": "东大街以北、静安路以南片区",
                "mapping_status": "verified",
            },
            current_version=1,
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/review/mappings/{policy_id}/decision",
            data={
                "year": "2026",
                "district": "jinjiang",
                "status": "pending_review",
                "current_status": "pending_review",
                "review_decision": "reference",
            },
            follow_redirects=False,
        )

    assert resp.status_code == 303
    assert "message=stale" in resp.headers["location"]
    policy = await db_session.get(EnrollmentPolicy, policy_id)
    assert policy.fields["mapping_status"] == "verified"
    assert policy.current_version == 1


@pytest.mark.asyncio
async def test_mapping_review_decision_post_requires_token_when_configured(
    app, db_session, seeded_data, monkeypatch
):
    monkeypatch.setenv("ENABLE_REVIEW_WRITE", "true")
    monkeypatch.setenv("REVIEW_WRITE_TOKEN", "secret-token")
    jinjiang_id = await _district_id(db_session, "jinjiang")
    pending_school_id = await _school_id(db_session, "锦江第一小学")
    policy_id = uuid.uuid4()
    db_session.add(
        EnrollmentPolicy(
            id=policy_id,
            district_id=jinjiang_id,
            school_id=pending_school_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2026,
            fields={
                "enrollment_scope": "东大街以北、静安路以南片区",
                "mapping_status": "pending_review",
            },
            current_version=1,
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        page = await client.get("/review/mappings")
        bad = await client.post(
            f"/review/mappings/{policy_id}/decision",
            data={
                "year": "2026",
                "district": "jinjiang",
                "status": "pending_review",
                "current_status": "pending_review",
                "review_decision": "verified",
                "review_token": "wrong",
            },
        )
        good = await client.post(
            f"/review/mappings/{policy_id}/decision",
            data={
                "year": "2026",
                "district": "jinjiang",
                "status": "pending_review",
                "current_status": "pending_review",
                "review_decision": "verified",
                "review_token": "secret-token",
            },
            follow_redirects=False,
        )

    assert page.status_code == 200
    assert "写入令牌" in page.text
    assert bad.status_code == 403
    assert good.status_code == 303
