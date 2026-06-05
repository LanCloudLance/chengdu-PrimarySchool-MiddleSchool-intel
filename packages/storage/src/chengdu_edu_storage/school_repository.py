from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import SchoolLevel, SchoolType
from chengdu_edu_storage.orm import District, School


class SchoolRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_school(
        self,
        *,
        name: str,
        district_id: UUID,
        type: SchoolType,
        level: SchoolLevel,
        short_name: str | None = None,
        address: str | None = None,
        source_urls: dict | None = None,
        metadata: dict | None = None,
    ) -> UUID:
        stmt = select(School).where(
            School.district_id == district_id,
            School.name == name,
        )
        result = await self.session.execute(stmt)
        school = result.scalar_one_or_none()

        urls = source_urls or {}
        meta = metadata or {}

        if school is None:
            school = School(
                name=name,
                district_id=district_id,
                type=type,
                level=level,
                short_name=short_name,
                address=address,
                source_urls=urls,
                metadata_=meta,
            )
            self.session.add(school)
        else:
            school.type = type
            school.level = level
            school.short_name = short_name
            school.address = address
            school.source_urls = urls
            school.metadata_ = meta

        await self.session.commit()
        await self.session.refresh(school)
        return school.id

    async def search(
        self,
        *,
        district_code: str | None = None,
        school_type: SchoolType | None = None,
        level: SchoolLevel | None = None,
        q: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[School]:
        stmt = select(School).join(District)
        if district_code:
            stmt = stmt.where(District.code == district_code)
        if school_type:
            stmt = stmt.where(School.type == school_type)
        if level:
            stmt = stmt.where(School.level == level)
        if q:
            stmt = stmt.where(School.name.ilike(f"%{q}%"))
        stmt = stmt.order_by(School.name).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_district_code_map(self) -> dict[str, UUID]:
        result = await self.session.execute(select(District))
        return {district.code: district.id for district in result.scalars().all()}
