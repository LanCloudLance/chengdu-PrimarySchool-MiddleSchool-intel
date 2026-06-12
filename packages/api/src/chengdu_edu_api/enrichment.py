from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import PolicyType, RecordType
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

POLICY_FIELD_LABELS: dict[str, str] = {
    "enrollment_scope": "招生范围",
    "registration_time": "登记时间",
    "requirements": "招生条件",
    "contact": "咨询电话",
    "notes": "备注",
    "registration_point_address": "登记点地址",
    "contact_phone": "联系电话",
    "contact_channel": "联系渠道",
    "source_page": "信息来源",
    "registration_guide": "登记点公告",
    "mapping_status": "划片状态",
    "reference_year": "参考年份",
    "promotion_overview": "小升初概要",
    "district_mapping_note": "划片/升学公布",
    "lottery_note": "摇号/随机录取",
    "direct_admission_note": "直升/一贯制",
    "registration_platform": "报名平台",
    "promotion_type": "升学方式",
    "target_schools": "对口初中",
    "target_school_name": "对口初中（主目标）",
    "target_source": "对口依据",
}

POLICY_TYPE_LABELS: dict[str, str] = {
    "gov_policy": "区级统一政策",
    "school_enrollment": "本校登记点信息",
    "district_mapping": "划片映射",
}


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


async def list_district_enrollment_policies(
    session: AsyncSession,
    district_id: UUID,
) -> list[EnrollmentPolicy]:
    stmt = (
        select(EnrollmentPolicy)
        .where(
            EnrollmentPolicy.district_id == district_id,
            EnrollmentPolicy.school_id.is_(None),
        )
        .order_by(EnrollmentPolicy.year.desc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def resolve_school_enrollment_policies(
    session: AsyncSession,
    *,
    district_id: UUID,
    school_policies: list[EnrollmentPolicy],
) -> tuple[list[EnrollmentPolicyOut], bool]:
    """本校登记点优先；划片映射单独保留；无本校数据时回退区级 gov_policy。"""
    mapping = [p for p in school_policies if p.policy_type == PolicyType.DISTRICT_MAPPING]
    school_only = [
        p for p in school_policies if p.policy_type != PolicyType.DISTRICT_MAPPING
    ]

    school_out = await build_enrollment_policy_outs(session, school_only)
    mapping_out = await build_enrollment_policy_outs(session, mapping)

    if school_out:
        district_policies = await list_district_enrollment_policies(session, district_id)
        district_out = await build_enrollment_policy_outs(session, district_policies)
        combined = school_out + mapping_out + [
            p for p in district_out if p.id not in {s.id for s in school_out + mapping_out}
        ]
        return combined, False

    if mapping_out:
        return mapping_out, False

    district_policies = await list_district_enrollment_policies(session, district_id)
    if not district_policies:
        return [], False
    return await build_enrollment_policy_outs(session, district_policies), True


async def build_promotion_policy_outs(
    session: AsyncSession, policies: list[PromotionPolicy]
) -> list[PromotionPolicyOut]:
    from chengdu_edu_storage.orm import School

    outs: list[PromotionPolicyOut] = []
    for policy in policies:
        out = await build_promotion_policy_out(session, policy)
        if policy.target_school_id:
            target = await session.get(School, policy.target_school_id)
            if target:
                fields = dict(out.fields)
                fields.setdefault("target_school_name", target.name)
                out = out.model_copy(update={"fields": fields})
        outs.append(out)
    return outs
