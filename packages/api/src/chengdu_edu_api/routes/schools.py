from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import RecordType, SchoolLevel, SchoolType
from chengdu_edu_core.search_query import school_fuzzy_filter
from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.enrichment import (
    resolve_school_enrollment_policies,
    build_promotion_policy_outs,
)
from chengdu_edu_api.schemas import (
    FieldChangeOut,
    PaginatedSchools,
    SchoolDetailOut,
    SchoolHistoryOut,
    SchoolSummary,
)
from chengdu_edu_storage.orm import District, FieldChange, School
from chengdu_edu_storage.repository import PolicyRepository

router = APIRouter(tags=["schools"])


def _school_filters(
    *,
    district_code: str | None,
    school_type: SchoolType | None,
    level: SchoolLevel | None,
    q: str | None,
):
    stmt = select(School, District.code).join(District, School.district_id == District.id)
    if district_code:
        stmt = stmt.where(District.code == district_code)
    if school_type:
        stmt = stmt.where(School.type == school_type)
    if level:
        stmt = stmt.where(School.level == level)
    fuzzy = school_fuzzy_filter(q, School.name, School.short_name, School.address)
    if fuzzy is not None:
        stmt = stmt.where(fuzzy)
    return stmt


@router.get("/schools", response_model=PaginatedSchools)
async def search_schools(
    district: str | None = None,
    type: SchoolType | None = None,
    level: SchoolLevel | None = None,
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedSchools:
    base = _school_filters(district_code=district, school_type=type, level=level, q=q)
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = base.order_by(School.name).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()
    items = [
        SchoolSummary(
            id=school.id,
            name=school.name,
            short_name=school.short_name,
            district_id=school.district_id,
            district_code=district_code,
            type=school.type,
            level=school.level,
            address=school.address,
        )
        for school, district_code in rows
    ]
    return PaginatedSchools(items=items, total=total, offset=offset, limit=limit)


@router.get("/schools/{school_id}", response_model=SchoolDetailOut)
async def get_school(
    school_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> SchoolDetailOut:
    repo = PolicyRepository(session)
    data = await repo.get_school_with_policies(school_id)
    if data is None:
        raise HTTPException(status_code=404, detail="School not found")

    district = await session.get(District, data.school.district_id)
    district_code = district.code if district else ""

    enrollment, _ = await resolve_school_enrollment_policies(
        session,
        district_id=data.school.district_id,
        school_policies=data.enrollment_policies,
    )
    promotion = await build_promotion_policy_outs(session, data.promotion_policies)

    return SchoolDetailOut(
        id=data.school.id,
        name=data.school.name,
        short_name=data.school.short_name,
        district_id=data.school.district_id,
        district_code=district_code,
        type=data.school.type,
        level=data.school.level,
        address=data.school.address,
        source_urls=data.school.source_urls or {},
        metadata=data.school.metadata_ or {},
        enrollment_policies=enrollment,
        promotion_policies=promotion,
    )


@router.get("/schools/{school_id}/history", response_model=SchoolHistoryOut)
async def get_school_history(
    school_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> SchoolHistoryOut:
    school = await session.get(School, school_id)
    if school is None:
        raise HTTPException(status_code=404, detail="School not found")

    repo = PolicyRepository(session)
    data = await repo.get_school_with_policies(school_id)
    assert data is not None

    record_ids: list[UUID] = []
    for policy in data.enrollment_policies:
        record_ids.append(policy.id)
    for policy in data.promotion_policies:
        record_ids.append(policy.id)

    if not record_ids:
        return SchoolHistoryOut(school_id=school_id, changes=[])

    stmt = (
        select(FieldChange)
        .where(FieldChange.record_id.in_(record_ids))
        .order_by(FieldChange.detected_at.desc())
    )
    changes = list((await session.execute(stmt)).scalars().all())
    return SchoolHistoryOut(
        school_id=school_id,
        changes=[FieldChangeOut.model_validate(change) for change in changes],
    )
