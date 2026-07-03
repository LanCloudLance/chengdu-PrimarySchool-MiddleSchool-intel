import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from chengdu_edu_core.enums import PolicyType, SchoolLevel, SchoolType
from chengdu_edu_storage.orm import District, EnrollmentPolicy, School


async def _seed_year_switch_school(db_session):
    district_id = (
        await db_session.execute(select(District.id).where(District.code == "wuhou"))
    ).scalar_one()
    school_id = uuid.uuid4()
    db_session.add(
        School(
            id=school_id,
            name="年份切换实验小学",
            district_id=district_id,
            type=SchoolType.PUBLIC,
            level=SchoolLevel.PRIMARY,
            address="年度路1号",
        )
    )
    db_session.add_all(
        [
            EnrollmentPolicy(
                id=uuid.uuid4(),
                district_id=district_id,
                school_id=school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=2025,
                fields={
                    "enrollment_scope": "旧年街道2025片区",
                    "mapping_status": "verified",
                    "framework_year": 2025,
                },
                current_version=1,
            ),
            EnrollmentPolicy(
                id=uuid.uuid4(),
                district_id=district_id,
                school_id=school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=2026,
                fields={
                    "enrollment_scope": "新年街道2026片区",
                    "mapping_status": "pending_review",
                    "framework_year": 2026,
                },
                current_version=1,
            ),
        ]
    )
    await db_session.commit()
    return school_id


@pytest.mark.asyncio
async def test_api_school_search_uses_selected_mapping_year(
    app, db_session, seeded_data
):
    await _seed_year_switch_school(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_2025 = await client.get(
            "/api/schools",
            params={"q": "年份切换", "district": "wuhou", "year": 2025},
        )
        resp_2026 = await client.get(
            "/api/schools",
            params={"q": "年份切换", "district": "wuhou", "year": 2026},
        )

    assert resp_2025.status_code == 200
    item_2025 = resp_2025.json()["items"][0]
    assert item_2025["mapping_status"] == "verified"
    assert item_2025["framework_year"] == 2025

    assert resp_2026.status_code == 200
    item_2026 = resp_2026.json()["items"][0]
    assert item_2026["mapping_status"] == "pending_review"
    assert item_2026["framework_year"] == 2026


@pytest.mark.asyncio
async def test_api_scope_search_is_limited_to_selected_year(
    app, db_session, seeded_data
):
    await _seed_year_switch_school(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        old_scope_in_2026 = await client.get(
            "/api/schools",
            params={"scope_q": "旧年街道", "district": "wuhou", "year": 2026},
        )
        old_scope_in_2025 = await client.get(
            "/api/schools",
            params={"scope_q": "旧年街道", "district": "wuhou", "year": 2025},
        )

    assert old_scope_in_2026.status_code == 200
    assert old_scope_in_2026.json()["total"] == 0
    assert old_scope_in_2025.status_code == 200
    assert old_scope_in_2025.json()["total"] == 1


@pytest.mark.asyncio
async def test_index_page_links_results_to_selected_year(app, db_session, seeded_data):
    school_id = await _seed_year_switch_school(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/",
            params={"q": "年份切换", "district": "wuhou", "year": 2025},
        )

    assert resp.status_code == 200
    assert f"/schools/{school_id}?year=2025" in resp.text
    assert "已核实" in resp.text
    assert "待复核" not in resp.text


@pytest.mark.asyncio
async def test_index_page_accepts_blank_select_values(app, db_session, seeded_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/",
            params={
                "year": 2026,
                "q": "",
                "scope_q": "",
                "district": "",
                "type": "",
                "level": "",
            },
        )

    assert resp.status_code == 200
    assert "学校搜索" in resp.text


@pytest.mark.asyncio
async def test_school_detail_page_uses_selected_year(app, db_session, seeded_data):
    school_id = await _seed_year_switch_school(db_session)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp_2025 = await client.get(f"/schools/{school_id}", params={"year": 2025})
        resp_2026 = await client.get(f"/schools/{school_id}", params={"year": 2026})

    assert resp_2025.status_code == 200
    assert "旧年街道2025片区" in resp_2025.text
    assert "新年街道2026片区" not in resp_2025.text
    assert "2025 年框架" in resp_2025.text

    assert resp_2026.status_code == 200
    assert "新年街道2026片区" in resp_2026.text
    assert "旧年街道2025片区" not in resp_2026.text
    assert "2026 年框架" in resp_2026.text
