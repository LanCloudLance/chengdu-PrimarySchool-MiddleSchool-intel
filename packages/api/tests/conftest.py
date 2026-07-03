import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from chengdu_edu_core.enums import DistrictLevel, SchoolLevel, SchoolType
from chengdu_edu_storage.orm import Base, District, School


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def seeded_data(db_session):
    districts = [
        ("锦江区", "jinjiang"),
        ("青羊区", "qingyang"),
        ("武侯区", "wuhou"),
        ("成华区", "chenghua"),
        ("金牛区", "jinniu"),
        ("高新区", "gaoxin"),
        ("天府新区", "tianfu"),
    ]
    district_ids: dict[str, uuid.UUID] = {}
    for name, code in districts:
        district_id = uuid.uuid4()
        district_ids[code] = district_id
        db_session.add(
            District(
                id=district_id,
                name=name,
                code=code,
                level=DistrictLevel.CORE,
            )
        )

    db_session.add_all(
        [
            School(
                id=uuid.uuid4(),
                name="成都七中实验学校",
                district_id=district_ids["jinjiang"],
                type=SchoolType.PUBLIC,
                level=SchoolLevel.MIDDLE,
            ),
            School(
                id=uuid.uuid4(),
                name="锦江第一小学",
                district_id=district_ids["jinjiang"],
                type=SchoolType.PUBLIC,
                level=SchoolLevel.PRIMARY,
            ),
            School(
                id=uuid.uuid4(),
                name="武侯实验中学",
                district_id=district_ids["wuhou"],
                type=SchoolType.PUBLIC,
                level=SchoolLevel.MIDDLE,
            ),
        ]
    )
    await db_session.commit()


@pytest.fixture
def app(db_session):
    from chengdu_edu_api.dependencies import get_db_session
    from chengdu_edu_api.main import app as fastapi_app

    async def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db_session] = override_get_db
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()
