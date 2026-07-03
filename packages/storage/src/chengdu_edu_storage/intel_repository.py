from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import IntelType
from chengdu_edu_storage.orm import IntelEntry


class IntelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def find_by_hash(self, content_hash: str) -> IntelEntry | None:
        stmt = select(IntelEntry).where(IntelEntry.content_hash == content_hash).limit(1)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def upsert_entry(
        self,
        *,
        district_id: UUID,
        school_id: UUID | None,
        intel_type: IntelType,
        source_url: str,
        source_title: str | None,
        content_hash: str,
        raw_text: str | None,
        structured_fields: dict,
        data_year: int,
        is_reference: bool = False,
    ) -> IntelEntry:
        stmt = select(IntelEntry).where(
            IntelEntry.district_id == district_id,
            IntelEntry.intel_type == intel_type,
            IntelEntry.source_url == source_url,
            IntelEntry.data_year == data_year,
        )
        if school_id:
            stmt = stmt.where(IntelEntry.school_id == school_id)
        else:
            stmt = stmt.where(IntelEntry.school_id.is_(None))

        entry = (await self.session.execute(stmt.limit(1))).scalar_one_or_none()
        now = datetime.now(timezone.utc)

        if entry is None:
            entry = IntelEntry(
                district_id=district_id,
                school_id=school_id,
                intel_type=intel_type,
                source_url=source_url,
                source_title=source_title,
                content_hash=content_hash,
                raw_text=raw_text,
                structured_fields=structured_fields,
                data_year=data_year,
                collected_at=now,
                is_reference=is_reference,
            )
            self.session.add(entry)
        elif entry.content_hash == content_hash:
            if entry.structured_fields != structured_fields:
                entry.structured_fields = structured_fields
                entry.source_title = source_title
                entry.collected_at = now
                await self.session.commit()
                await self.session.refresh(entry)
            return entry
        else:
            entry.content_hash = content_hash
            entry.raw_text = raw_text
            entry.structured_fields = structured_fields
            entry.source_title = source_title
            entry.collected_at = now
            entry.is_reference = is_reference

        await self.session.commit()
        await self.session.refresh(entry)
        return entry

    async def list_district_intel(
        self,
        *,
        district_id: UUID,
        intel_type: IntelType,
        data_year: int | None = None,
    ) -> list[IntelEntry]:
        stmt = select(IntelEntry).where(
            IntelEntry.district_id == district_id,
            IntelEntry.intel_type == intel_type,
        )
        if data_year is not None:
            stmt = stmt.where(IntelEntry.data_year == data_year)
        stmt = stmt.order_by(IntelEntry.data_year.desc(), IntelEntry.collected_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())
