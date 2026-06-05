from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import PolicyType, SchoolLevel, SchoolType
from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.enrichment import (
    build_enrollment_policy_outs,
    build_promotion_policy_outs,
)
from chengdu_edu_api.routes.policies import _enrollment_filters
from chengdu_edu_api.routes.schools import _school_filters
from chengdu_edu_api.schemas import FieldChangeOut
from chengdu_edu_storage.orm import District, EnrollmentPolicy, FieldChange, School
from chengdu_edu_storage.repository import PolicyRepository

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["pages"])

SCHOOL_TYPE_LABELS = {
    SchoolType.PUBLIC: "公办",
    SchoolType.PRIVATE: "民办",
}

SCHOOL_LEVEL_LABELS = {
    SchoolLevel.PRIMARY: "小学",
    SchoolLevel.MIDDLE: "初中",
    SchoolLevel.NINE_YEAR: "九年一贯制",
}


async def _load_districts(session: AsyncSession) -> list[District]:
    result = await session.execute(select(District).order_by(District.name))
    return list(result.scalars().all())


@router.get("/")
async def index_page(
    request: Request,
    district: str | None = None,
    type: SchoolType | None = None,
    level: SchoolLevel | None = None,
    q: str | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    districts = await _load_districts(session)
    schools: list[tuple[School, str]] = []
    total = 0

    if q or district or type or level:
        base = _school_filters(district_code=district, school_type=type, level=level, q=q)
        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await session.execute(count_stmt)).scalar_one()
        stmt = base.order_by(School.name).offset(offset).limit(limit)
        schools = list((await session.execute(stmt)).all())

    context = {
        "request": request,
        "districts": districts,
        "schools": schools,
        "total": total,
        "q": q or "",
        "district": district or "",
        "type": type.value if type else "",
        "level": level.value if level else "",
        "school_type_labels": SCHOOL_TYPE_LABELS,
        "school_level_labels": SCHOOL_LEVEL_LABELS,
    }

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse("school_results.html", context)

    return templates.TemplateResponse("index.html", context)


@router.get("/schools/{school_id}")
async def school_detail_page(
    request: Request,
    school_id: UUID,
    session: AsyncSession = Depends(get_db_session),
):
    repo = PolicyRepository(session)
    data = await repo.get_school_with_policies(school_id)
    if data is None:
        raise HTTPException(status_code=404, detail="School not found")

    district = await session.get(District, data.school.district_id)
    enrollment = await build_enrollment_policy_outs(session, data.enrollment_policies)
    promotion = await build_promotion_policy_outs(session, data.promotion_policies)

    record_ids = [p.id for p in data.enrollment_policies] + [
        p.id for p in data.promotion_policies
    ]
    changes: list[FieldChangeOut] = []
    if record_ids:
        stmt = (
            select(FieldChange)
            .where(FieldChange.record_id.in_(record_ids))
            .order_by(FieldChange.detected_at.desc())
            .limit(50)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        changes = [FieldChangeOut.model_validate(change) for change in rows]

    return templates.TemplateResponse(
        "school_detail.html",
        {
            "request": request,
            "school": data.school,
            "district": district,
            "enrollment_policies": enrollment,
            "promotion_policies": promotion,
            "changes": changes,
            "school_type_labels": SCHOOL_TYPE_LABELS,
            "school_level_labels": SCHOOL_LEVEL_LABELS,
        },
    )


@router.get("/policies/government")
async def gov_policies_page(
    request: Request,
    district: str | None = None,
    year: int | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    districts = await _load_districts(session)
    active_district = district or (districts[0].code if districts else None)

    base = _enrollment_filters(
        district_code=active_district,
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

    return templates.TemplateResponse(
        "gov_policies.html",
        {
            "request": request,
            "districts": districts,
            "active_district": active_district,
            "policies": items,
            "total": total,
            "year": year,
        },
    )
