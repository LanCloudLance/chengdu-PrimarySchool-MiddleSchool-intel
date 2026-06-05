from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.diff import compute_field_changes
from chengdu_edu_core.enums import PolicyType, RecordType, SchoolLevel, SchoolType
from chengdu_edu_core.models import FieldChange as FieldChangeDTO
from chengdu_edu_storage.orm import (
    District,
    EnrollmentPolicy,
    FieldChange,
    RecordVersion,
    School,
)


class PolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_enrollment(
        self,
        *,
        district_id: UUID,
        school_id: UUID | None,
        policy_type: PolicyType,
        year: int,
        fields: dict,
        source_doc_id: UUID,
        confidence: float,
        existing_id: UUID | None = None,
    ) -> UUID:
        if existing_id:
            policy = await self.session.get(EnrollmentPolicy, existing_id)
            old_fields = dict(policy.fields)
            if old_fields == fields:
                return existing_id
            changes = compute_field_changes(old_fields, fields)
            policy.fields = fields
            policy.current_version += 1
            policy.source_doc_id = source_doc_id
            policy.confidence = confidence
            self._add_version(
                RecordType.ENROLLMENT,
                policy.id,
                policy.current_version,
                fields,
                source_doc_id,
            )
            for change in changes:
                self._add_field_change(
                    RecordType.ENROLLMENT,
                    policy.id,
                    policy.current_version - 1,
                    policy.current_version,
                    change,
                )
        else:
            policy = EnrollmentPolicy(
                district_id=district_id,
                school_id=school_id,
                policy_type=policy_type,
                year=year,
                fields=fields,
                source_doc_id=source_doc_id,
                confidence=confidence,
                current_version=1,
            )
            self.session.add(policy)
            await self.session.flush()
            self._add_version(RecordType.ENROLLMENT, policy.id, 1, fields, source_doc_id)
        await self.session.commit()
        return policy.id

    async def get_field_changes(
        self, record_type: RecordType, record_id: UUID
    ) -> list[FieldChange]:
        stmt = (
            select(FieldChange)
            .where(
                FieldChange.record_type == record_type,
                FieldChange.record_id == record_id,
            )
            .order_by(FieldChange.detected_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search_schools(
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
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _add_version(
        self,
        record_type: RecordType,
        record_id: UUID,
        version: int,
        fields_snapshot: dict,
        source_doc_id: UUID | None,
    ) -> None:
        self.session.add(
            RecordVersion(
                record_type=record_type,
                record_id=record_id,
                version=version,
                fields_snapshot=fields_snapshot,
                source_doc_id=source_doc_id,
                created_at=datetime.now(timezone.utc),
            )
        )

    def _add_field_change(
        self,
        record_type: RecordType,
        record_id: UUID,
        from_version: int,
        to_version: int,
        change: FieldChangeDTO,
    ) -> None:
        self.session.add(
            FieldChange(
                record_type=record_type,
                record_id=record_id,
                from_version=from_version,
                to_version=to_version,
                field_path=change.field_path,
                old_value=change.old_value or None,
                new_value=change.new_value or None,
                detected_at=datetime.now(timezone.utc),
            )
        )
