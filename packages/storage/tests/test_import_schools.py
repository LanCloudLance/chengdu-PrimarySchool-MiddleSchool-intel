import sys
from pathlib import Path

import pytest
import pytest_asyncio

from chengdu_edu_core.enums import DistrictLevel
from chengdu_edu_storage.orm import District
from chengdu_edu_storage.school_repository import SchoolRepository

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from import_schools import import_schools_from_yaml  # noqa: E402

SCHOOLS_YAML = ROOT / "configs" / "schools.yaml"


@pytest_asyncio.fixture
async def seeded_districts(db_session):
    districts = [
        District(name="锦江区", code="jinjiang", level=DistrictLevel.CORE),
        District(name="青羊区", code="qingyang", level=DistrictLevel.CORE),
        District(name="武侯区", code="wuhou", level=DistrictLevel.CORE),
        District(name="成华区", code="chenghua", level=DistrictLevel.CORE),
        District(name="金牛区", code="jinniu", level=DistrictLevel.CORE),
        District(name="高新区", code="gaoxin", level=DistrictLevel.CORE),
        District(name="天府新区", code="tianfu", level=DistrictLevel.CORE),
    ]
    db_session.add_all(districts)
    await db_session.commit()
    return districts


@pytest.mark.asyncio
async def test_import_schools_from_yaml(db_session, seeded_districts):
    repo = SchoolRepository(db_session)
    count = await import_schools_from_yaml(SCHOOLS_YAML, repo)
    assert count == 0
