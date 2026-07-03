from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import PolicyType, RecordType
from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.enrichment import (
    build_enrollment_policy_out,
    build_enrollment_policy_outs,
    build_promotion_policy_outs,
)
from chengdu_edu_api.schemas import (
    EnrollmentPolicyOut,
    FieldChangeOut,
    PaginatedEnrollmentPolicies,
    PaginatedPromotionPolicies,
)
from chengdu_edu_storage.orm import District, EnrollmentPolicy, PromotionPolicy
from chengdu_edu_storage.repository import PolicyRepository

router = APIRouter(prefix="/policies", tags=["policies"])


def _enrollment_filters(
    *,
    district_code: str | None,
    school_id: UUID | None,
    policy_type: PolicyType | None,
    year: int | None,
):
    stmt = select(EnrollmentPolicy).join(District)
    if district_code:
        stmt = stmt.where(District.code == district_code)
    if school_id is not None:
        stmt = stmt.where(EnrollmentPolicy.school_id == school_id)
    if policy_type is not None:
        stmt = stmt.where(EnrollmentPolicy.policy_type == policy_type)
    if year is not None:
        stmt = stmt.where(EnrollmentPolicy.year == year)
    return stmt


@router.get("/enrollment", response_model=PaginatedEnrollmentPolicies)
async def search_enrollment_policies(
    district: str | None = None,
    school_id: UUID | None = None,
    year: int | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedEnrollmentPolicies:
    base = _enrollment_filters(
        district_code=district,
        school_id=school_id,
        policy_type=PolicyType.SCHOOL_ENROLLMENT,
        year=year,
    )
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(EnrollmentPolicy.year.desc()).offset(offset).limit(limit)
    policies = list((await session.execute(stmt)).scalars().all())
    items = await build_enrollment_policy_outs(session, policies)
    return PaginatedEnrollmentPolicies(
        items=items, total=total, offset=offset, limit=limit
    )


@router.get("/enrollment/{policy_id}", response_model=EnrollmentPolicyOut)
async def get_enrollment_policy(
    policy_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> EnrollmentPolicyOut:
    policy = await session.get(EnrollmentPolicy, policy_id)
    if policy is None or policy.policy_type != PolicyType.SCHOOL_ENROLLMENT:
        raise HTTPException(status_code=404, detail="Enrollment policy not found")
    return await build_enrollment_policy_out(session, policy)


@router.get("/enrollment/{policy_id}/changes", response_model=list[FieldChangeOut])
async def get_enrollment_policy_changes(
    policy_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> list[FieldChangeOut]:
    policy = await session.get(EnrollmentPolicy, policy_id)
    if policy is None or policy.policy_type != PolicyType.SCHOOL_ENROLLMENT:
        raise HTTPException(status_code=404, detail="Enrollment policy not found")
    repo = PolicyRepository(session)
    changes = await repo.get_field_changes(RecordType.ENROLLMENT, policy_id)
    return [FieldChangeOut.model_validate(change) for change in changes]


@router.get("/promotion", response_model=PaginatedPromotionPolicies)
async def search_promotion_policies(
    district: str | None = None,
    school_id: UUID | None = None,
    year: int | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedPromotionPolicies:
    stmt = select(PromotionPolicy).join(District)
    if district:
        stmt = stmt.where(District.code == district)
    if school_id is not None:
        stmt = stmt.where(PromotionPolicy.school_id == school_id)
    if year is not None:
        stmt = stmt.where(PromotionPolicy.year == year)

    total = (
        await session.execute(select(func.count()).select_from(stmt.subquery()))
    ).scalar_one()
    policies = list(
        (
            await session.execute(
                stmt.order_by(PromotionPolicy.year.desc()).offset(offset).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    items = await build_promotion_policy_outs(session, policies)
    return PaginatedPromotionPolicies(
        items=items, total=total, offset=offset, limit=limit
    )


@router.get("/government", response_model=PaginatedEnrollmentPolicies)
async def search_government_policies(
    district: str | None = None,
    year: int | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedEnrollmentPolicies:
    base = _enrollment_filters(
        district_code=district,
        school_id=None,
        policy_type=PolicyType.GOV_POLICY,
        year=year,
    )
    total = (
        await session.execute(select(func.count()).select_from(base.subquery()))
    ).scalar_one()
    stmt = base.order_by(EnrollmentPolicy.year.desc()).offset(offset).limit(limit)
    policies = list((await session.execute(stmt)).scalars().all())
    items = await build_enrollment_policy_outs(session, policies)
    return PaginatedEnrollmentPolicies(
        items=items, total=total, offset=offset, limit=limit
    )
