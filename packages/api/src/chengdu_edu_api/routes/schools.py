from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import PolicyType, SchoolLevel, SchoolType
from chengdu_edu_core.search_query import school_fuzzy_filter
from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.enrichment import (
    resolve_school_enrollment_policies,
    build_promotion_policy_outs,
)
from chengdu_edu_api.mapping_display import batch_district_mapping_summaries
from chengdu_edu_api.schemas import (
    FieldChangeOut,
    PaginatedSchools,
    SchoolDetailOut,
    SchoolHistoryOut,
    SchoolSummary,
)
from chengdu_edu_storage.orm import District, EnrollmentPolicy, FieldChange, School
from chengdu_edu_storage.repository import PolicyRepository

router = APIRouter(tags=["schools"])


def _coerce_school_type(value: SchoolType | str | None) -> SchoolType | None:
    if value is None or value == "":
        return None
    if isinstance(value, SchoolType):
        return value
    try:
        return SchoolType(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid school type") from exc


def _coerce_school_level(value: SchoolLevel | str | None) -> SchoolLevel | None:
    if value is None or value == "":
        return None
    if isinstance(value, SchoolLevel):
        return value
    try:
        return SchoolLevel(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid school level") from exc


def _school_filters(
    *,
    district_code: str | None,
    school_type: SchoolType | str | None,
    level: SchoolLevel | str | None,
    q: str | None,
    scope_q: str | None = None,
    year: int | None = None,
):
    school_type = _coerce_school_type(school_type)
    level = _coerce_school_level(level)
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
    if scope_q and scope_q.strip():
        scope_col = cast(EnrollmentPolicy.fields["enrollment_scope"], String)
        stmt = stmt.join(
            EnrollmentPolicy,
            (EnrollmentPolicy.school_id == School.id)
            & (EnrollmentPolicy.policy_type == PolicyType.DISTRICT_MAPPING),
        )
        if year is not None:
            stmt = stmt.where(EnrollmentPolicy.year == year)
        scope_filter = school_fuzzy_filter(scope_q, scope_col)
        if scope_filter is not None:
            stmt = stmt.where(scope_filter)
        stmt = stmt.distinct()
    return stmt


def _summary_from_row(
    school: School,
    district_code: str,
    mapping_fields: dict | None,
) -> SchoolSummary:
    fields = mapping_fields or {}
    return SchoolSummary(
        id=school.id,
        name=school.name,
        short_name=school.short_name,
        district_id=school.district_id,
        district_code=district_code,
        type=school.type,
        level=school.level,
        address=school.address,
        mapping_status=fields.get("mapping_status"),
        framework_year=fields.get("framework_year"),
        reference_year=fields.get("reference_year"),
        source_page=fields.get("source_page"),
    )


@router.get("/schools", response_model=PaginatedSchools)
async def search_schools(
    district: str | None = None,
    type: str | None = None,
    level: str | None = None,
    q: str | None = None,
    scope_q: str | None = Query(
        default=None,
        description="划片范围/街道地址关键词（搜索 district_mapping.enrollment_scope）",
    ),
    year: int | None = Query(
        default=None,
        ge=2000,
        le=2100,
        description="划片年份；为空时使用每所学校最新划片记录",
    ),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedSchools:
    base = _school_filters(
        district_code=district,
        school_type=type,
        level=level,
        q=q,
        scope_q=scope_q,
        year=year,
    )
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    stmt = base.order_by(School.name).offset(offset).limit(limit)
    rows = (await session.execute(stmt)).all()
    school_ids = [school.id for school, _dc in rows]
    mapping_map = await batch_district_mapping_summaries(session, school_ids, year=year)
    items = [
        _summary_from_row(school, district_code, mapping_map.get(school.id))
        for school, district_code in rows
    ]
    return PaginatedSchools(items=items, total=total, offset=offset, limit=limit)


@router.get("/schools/{school_id}", response_model=SchoolDetailOut)
async def get_school(
    school_id: UUID,
    year: int | None = Query(default=None, ge=2000, le=2100),
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
        year=year,
    )
    promotion_policies = (
        [p for p in data.promotion_policies if p.year == year]
        if year is not None
        else data.promotion_policies
    )
    promotion = await build_promotion_policy_outs(session, promotion_policies)

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
