import pytest
from sqlalchemy import select

from chengdu_edu_core.enums import DistrictLevel
from chengdu_edu_storage.orm import District


@pytest.mark.asyncio
async def test_district_table_exists(db_session):
    district = District(name="锦江区", code="jinjiang", level=DistrictLevel.CORE)
    db_session.add(district)
    await db_session.commit()
    result = await db_session.execute(select(District).where(District.code == "jinjiang"))
    row = result.scalar_one()
    assert row.name == "锦江区"
