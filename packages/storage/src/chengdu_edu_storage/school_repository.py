from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import SchoolLevel, SchoolType
from chengdu_edu_core.search_query import school_fuzzy_filter
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
        former_names: list[str] | None = None,
    ) -> UUID:
        stmt = select(School).where(
            School.district_id == district_id,
            School.name == name,
        )
        result = await self.session.execute(stmt)
        school = result.scalar_one_or_none()

        if school is None and former_names:
            for old_name in former_names:
                legacy_stmt = select(School).where(
                    School.district_id == district_id,
                    School.name == old_name,
                )
                school = (await self.session.execute(legacy_stmt)).scalar_one_or_none()
                if school is not None:
                    school.name = name
                    break

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
        fuzzy = school_fuzzy_filter(q, School.name, School.short_name, School.address)
        if fuzzy is not None:
            stmt = stmt.where(fuzzy)
        stmt = stmt.order_by(School.name).offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def find_school_id(
        self, *, district_id: UUID, name: str
    ) -> UUID | None:
        stmt = select(School.id).where(
            School.district_id == district_id,
            School.name == name,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def prune_orphan_schools(
        self, *, district_id: UUID, keep_names: set[str]
    ) -> int:
        """删除区内不在 keep_names 中的学校（用于清理历史重复导入）。"""
        stmt = select(School).where(School.district_id == district_id)
        schools = list((await self.session.execute(stmt)).scalars().all())
        removed = 0
        for school in schools:
            if school.name in keep_names:
                continue
            await self.session.delete(school)
            removed += 1
        if removed:
            await self.session.commit()
        return removed

    async def get_district_code_map(self) -> dict[str, UUID]:
        result = await self.session.execute(select(District))
        return {district.code: district.id for district in result.scalars().all()}
