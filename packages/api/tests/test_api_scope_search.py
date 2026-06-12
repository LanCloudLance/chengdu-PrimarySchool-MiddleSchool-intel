import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from chengdu_edu_core.enums import PolicyType, SchoolLevel, SchoolType
from chengdu_edu_storage.orm import District, EnrollmentPolicy, School


@pytest.mark.asyncio
async def test_search_schools_by_scope_q(app, db_session, seeded_data):
    wuhou_id = (
        await db_session.execute(select(District.id).where(District.code == "wuhou"))
    ).scalar_one()

    primary_id = uuid.uuid4()
    db_session.add(
        School(
            id=primary_id,
            name="成都市玉林小学",
            district_id=wuhou_id,
            type=SchoolType.PUBLIC,
            level=SchoolLevel.PRIMARY,
            address="玉林东路1号",
        )
    )
    db_session.add(
        EnrollmentPolicy(
            id=uuid.uuid4(),
            district_id=wuhou_id,
            school_id=primary_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2025,
            fields={
                "enrollment_scope": "玉林东路、玉林西街一带",
                "mapping_status": "reference",
                "framework_year": 2025,
                "reference_year": 2024,
                "source_page": "http://example.com/mapping",
            },
            current_version=1,
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/schools",
            params={"scope_q": "玉林东路", "district": "wuhou"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    names = [item["name"] for item in data["items"]]
    assert "成都市玉林小学" in names
    item = next(i for i in data["items"] if i["name"] == "成都市玉林小学")
    assert item["mapping_status"] == "reference"
    assert item["framework_year"] == 2025
