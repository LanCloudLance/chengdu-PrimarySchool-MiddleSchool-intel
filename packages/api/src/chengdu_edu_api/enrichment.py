from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import RecordType
from chengdu_edu_storage.orm import (
    DataSource,
    EnrollmentPolicy,
    FieldChange,
    PromotionPolicy,
    RawDocument,
)

from chengdu_edu_api.schemas import (
    EnrollmentPolicyOut,
    PromotionPolicyOut,
    SourceMeta,
)


async def has_recent_changes(
    session: AsyncSession,
    record_type: RecordType,
    record_id: UUID,
    *,
    days: int = 30,
) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(FieldChange.id)
        .where(
            FieldChange.record_type == record_type,
            FieldChange.record_id == record_id,
            FieldChange.detected_at >= cutoff,
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() is not None


async def _load_source_meta(
    session: AsyncSession, source_doc_id: UUID | None
) -> tuple[str | None, datetime | None]:
    if source_doc_id is None:
        return None, None
    doc = await session.get(RawDocument, source_doc_id)
    if doc is None:
        return None, None
    source = await session.get(DataSource, doc.source_id)
    url = source.url if source else None
    return url, doc.fetched_at


async def build_enrollment_policy_out(
    session: AsyncSession, policy: EnrollmentPolicy
) -> EnrollmentPolicyOut:
    url, fetched_at = await _load_source_meta(session, policy.source_doc_id)
    recent = await has_recent_changes(session, RecordType.ENROLLMENT, policy.id)
    return EnrollmentPolicyOut(
        id=policy.id,
        school_id=policy.school_id,
        district_id=policy.district_id,
        policy_type=policy.policy_type,
        year=policy.year,
        fields=policy.fields,
        current_version=policy.current_version,
        source=SourceMeta(url=url),
        fetched_at=fetched_at,
        confidence=policy.confidence,
        has_recent_changes=recent,
    )


async def build_promotion_policy_out(
    session: AsyncSession, policy: PromotionPolicy
) -> PromotionPolicyOut:
    url, fetched_at = await _load_source_meta(session, policy.source_doc_id)
    recent = await has_recent_changes(session, RecordType.PROMOTION, policy.id)
    return PromotionPolicyOut(
        id=policy.id,
        school_id=policy.school_id,
        target_school_id=policy.target_school_id,
        district_id=policy.district_id,
        year=policy.year,
        fields=policy.fields,
        current_version=policy.current_version,
        source=SourceMeta(url=url),
        fetched_at=fetched_at,
        confidence=None,
        has_recent_changes=recent,
    )


async def build_enrollment_policy_outs(
    session: AsyncSession, policies: list[EnrollmentPolicy]
) -> list[EnrollmentPolicyOut]:
    return [await build_enrollment_policy_out(session, policy) for policy in policies]


async def build_promotion_policy_outs(
    session: AsyncSession, policies: list[PromotionPolicy]
) -> list[PromotionPolicyOut]:
    return [await build_promotion_policy_out(session, policy) for policy in policies]
