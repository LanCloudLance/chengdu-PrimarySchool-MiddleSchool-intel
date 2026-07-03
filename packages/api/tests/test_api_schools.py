import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_districts_returns_seven(app, db_session, seeded_data):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/districts")
    assert resp.status_code == 200
    assert len(resp.json()) == 7


@pytest.mark.asyncio
async def test_search_schools_by_query(app, db_session, seeded_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/schools", params={"q": "实验", "district": "jinjiang"})
    assert resp.status_code == 200
    assert resp.json()["total"] >= 0


@pytest.mark.asyncio
async def test_search_schools_accepts_blank_select_values(app, db_session, seeded_data):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/schools",
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
