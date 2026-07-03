import csv
import io
import os
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs
from urllib.parse import urlencode
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.diff import compute_field_changes
from chengdu_edu_core.enums import PolicyType, SchoolLevel, SchoolType
from chengdu_edu_core.enums import RecordType
from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.enrichment import (
    POLICY_FIELD_LABELS,
    POLICY_TYPE_LABELS,
    build_enrollment_policy_outs,
    build_promotion_policy_outs,
    resolve_school_enrollment_policies,
)
from chengdu_edu_api.mapping_display import (
    DISCLAIMER_TEXT,
    MAPPING_DECISION_STATUSES,
    MAPPING_STATUS_META,
    MAPPING_REVIEW_STATUSES,
    batch_district_mapping_summaries,
    mapping_provenance_lines,
    mapping_status_badge,
)
from chengdu_edu_api.routes.policies import _enrollment_filters
from chengdu_edu_api.routes.schools import _school_filters
from chengdu_edu_api.schemas import FieldChangeOut
from chengdu_edu_storage.orm import (
    District,
    EnrollmentPolicy,
    FieldChange,
    RecordVersion,
    School,
)
from chengdu_edu_storage.repository import PolicyRepository

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(tags=["pages"])

DEFAULT_MAPPING_YEAR = 2026
MAPPING_YEAR_OPTIONS = [2026, 2025]

_SCOPE_KW = re.compile(r"[至界路街道巷大道区社区苑村]")
_SCOPE_NOISE = re.compile(
    r"招生|报名|年满|条件|政策|电脑随机|录取|简章|户籍.*残疾|少年|儿童.*少年"
)


SCHOOL_TYPE_LABELS = {
    SchoolType.PUBLIC: "公办",
    SchoolType.PRIVATE: "民办",
}

SCHOOL_LEVEL_LABELS = {
    SchoolLevel.PRIMARY: "小学",
    SchoolLevel.MIDDLE: "初中",
    SchoolLevel.NINE_YEAR: "九年一贯制",
}

REVIEW_STATUS_OPTIONS = {
    "needs_review": "待复核/待官方",
    "pending_review": "待人工复核",
    "pending_official": "待官方确认",
    "reference": "参考",
    "verified": "已核实",
    "all": "全部",
}

TRUE_VALUES = {"1", "true", "yes", "on"}


def _is_dropdown_scope(text: str) -> bool:
    """判断是否为有效的划片范围文本（用于下拉框过滤）。"""
    if not text or len(text) < 8 or len(text) > 120:
        return False
    if _SCOPE_NOISE.search(text):
        return False
    return bool(_SCOPE_KW.search(text))


async def _load_districts(session: AsyncSession) -> list[District]:
    result = await session.execute(select(District).order_by(District.name))
    return list(result.scalars().all())


async def _load_school_mapping_years(
    session: AsyncSession,
    school_id: UUID,
) -> list[int]:
    result = await session.execute(
        select(EnrollmentPolicy.year)
        .where(
            EnrollmentPolicy.school_id == school_id,
            EnrollmentPolicy.policy_type == PolicyType.DISTRICT_MAPPING,
        )
        .distinct()
        .order_by(EnrollmentPolicy.year.desc())
    )
    return [int(year) for year in result.scalars().all()]


def _mapping_status(fields: dict | None) -> str:
    if not fields:
        return ""
    return str(fields.get("mapping_status") or "")


def _status_matches(status: str, selected: str) -> bool:
    if selected == "all":
        return True
    if selected == "needs_review":
        return status in MAPPING_REVIEW_STATUSES
    return status == selected


def _review_write_enabled() -> bool:
    return os.environ.get("ENABLE_REVIEW_WRITE", "").strip().lower() in TRUE_VALUES


def _review_write_token() -> str:
    return os.environ.get("REVIEW_WRITE_TOKEN", "").strip()


def _review_write_token_required() -> bool:
    return bool(_review_write_token())


def _review_write_authorized(submitted_token: str) -> bool:
    expected = _review_write_token()
    if not expected:
        return True
    return secrets.compare_digest(submitted_token, expected)


async def _mapping_review_rows(
    session: AsyncSession,
    *,
    district: str | None,
    selected_status: str,
    year: int,
) -> tuple[list[dict], dict[str, int]]:
    stmt = (
        select(EnrollmentPolicy, School, District)
        .join(School, EnrollmentPolicy.school_id == School.id)
        .join(District, EnrollmentPolicy.district_id == District.id)
        .where(
            EnrollmentPolicy.policy_type == PolicyType.DISTRICT_MAPPING,
            EnrollmentPolicy.year == year,
        )
        .order_by(District.name, School.name)
    )
    if district:
        stmt = stmt.where(District.code == district)

    rows = list((await session.execute(stmt)).all())
    status_counts = {key: 0 for key in MAPPING_STATUS_META}
    status_counts["unknown"] = 0
    review_rows = []

    for policy, school, row_district in rows:
        fields = dict(policy.fields or {})
        row_status = _mapping_status(fields)
        if row_status in status_counts:
            status_counts[row_status] += 1
        else:
            status_counts["unknown"] += 1
        if not _status_matches(row_status, selected_status):
            continue
        review_rows.append(
            {
                "policy": policy,
                "school": school,
                "district": row_district,
                "fields": fields,
                "status": row_status,
                "badge": mapping_status_badge(row_status),
                "provenance": mapping_provenance_lines(fields),
            }
        )

    return review_rows, status_counts


def _form_value(form: dict[str, list[str]], key: str) -> str:
    values = form.get(key) or [""]
    return values[0].strip()


def _review_return_url(
    *,
    year: str,
    district: str,
    status: str,
    message: str = "",
) -> str:
    query = urlencode(
        {
            "year": year,
            "district": district,
            "status": status,
            "message": message,
        }
    )
    return f"/review/mappings?{query}"


def _reviewed_mapping_fields(
    old_fields: dict,
    *,
    review_decision: str,
    review_notes: str,
    reviewed_by: str,
) -> dict:
    fields = dict(old_fields)
    old_status = _mapping_status(fields)
    fields["mapping_status"] = review_decision
    fields["reviewed_by"] = reviewed_by or "web_review"
    fields["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    fields["review_source"] = "mapping_review_web"
    if old_status != review_decision:
        fields["previous_mapping_status"] = old_status
    if review_notes:
        fields["review_notes"] = review_notes
    return fields


def _add_mapping_review_audit(
    session: AsyncSession,
    *,
    policy: EnrollmentPolicy,
    old_fields: dict,
    new_fields: dict,
) -> None:
    new_version = policy.current_version + 1
    policy.fields = new_fields
    policy.current_version = new_version
    session.add(
        RecordVersion(
            record_type=RecordType.ENROLLMENT,
            record_id=policy.id,
            version=new_version,
            fields_snapshot=new_fields,
            source_doc_id=policy.source_doc_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    for change in compute_field_changes(old_fields, new_fields):
        session.add(
            FieldChange(
                record_type=RecordType.ENROLLMENT,
                record_id=policy.id,
                from_version=new_version - 1,
                to_version=new_version,
                field_path=change.field_path,
                old_value=change.old_value or None,
                new_value=change.new_value or None,
                detected_at=datetime.now(timezone.utc),
            )
        )


@router.get("/")
async def index_page(
    request: Request,
    district: str | None = None,
    type: str | None = None,
    level: str | None = None,
    q: str | None = None,
    scope_q: str | None = None,
    year: int = Query(default=DEFAULT_MAPPING_YEAR, ge=2000, le=2100),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
):
    districts = await _load_districts(session)

    # 加载所有学校名称用于下拉选择（按区县分组）
    school_names_result = await session.execute(
        select(
            School.id,
            School.name,
            School.short_name,
            School.district_id,
            District.name.label("district_name"),
        )
        .join(District, School.district_id == District.id)
        .order_by(District.name, School.name)
    )
    all_school_names = [
        {
            "id": row.id,
            "name": row.name,
            "short_name": row.short_name or row.name,
            "district_name": row.district_name,
        }
        for row in school_names_result.all()
    ]

    # 加载所有片区用于下拉选择（过滤非划片文本）
    scope_col = EnrollmentPolicy.fields["enrollment_scope"].as_string().label("scope")
    scopes_subq = (
        select(scope_col)
        .where(
            EnrollmentPolicy.fields["enrollment_scope"].isnot(None),
            EnrollmentPolicy.policy_type == PolicyType.DISTRICT_MAPPING,
            EnrollmentPolicy.year == year,
        )
        .distinct()
        .subquery()
    )
    scopes_result = await session.execute(
        select(scopes_subq.c.scope).order_by(scopes_subq.c.scope)
    )
    all_scopes = [row.scope for row in scopes_result.all() if _is_dropdown_scope(row.scope)]

    schools: list[tuple[School, str]] = []
    mapping_summaries: dict = {}
    total = 0

    if q or scope_q or district or type or level:
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
        schools = list((await session.execute(stmt)).all())
        mapping_summaries = await batch_district_mapping_summaries(
            session, [s.id for s, _ in schools], year=year
        )

    context = {
        "request": request,
        "districts": districts,
        "all_school_names": all_school_names,
        "all_scopes": all_scopes,
        "schools": schools,
        "mapping_summaries": mapping_summaries,
        "mapping_status_meta": MAPPING_STATUS_META,
        "mapping_status_badge": mapping_status_badge,
        "total": total,
        "q": q or "",
        "scope_q": scope_q or "",
        "year": year,
        "mapping_year_options": MAPPING_YEAR_OPTIONS,
        "district": district or "",
        "type": type or "",
        "level": level or "",
        "school_type_labels": SCHOOL_TYPE_LABELS,
        "school_level_labels": SCHOOL_LEVEL_LABELS,
        "disclaimer": DISCLAIMER_TEXT,
    }

    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "school_results.html", context)

    return templates.TemplateResponse(request, "index.html", context)


@router.get("/review/mappings")
async def mapping_review_page(
    request: Request,
    district: str | None = None,
    status: str = Query(default="needs_review"),
    year: int = Query(default=2026, ge=2000, le=2100),
    message: str = "",
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=300),
    session: AsyncSession = Depends(get_db_session),
):
    districts = await _load_districts(session)
    selected_status = status if status in REVIEW_STATUS_OPTIONS else "needs_review"
    review_rows, status_counts = await _mapping_review_rows(
        session,
        district=district,
        selected_status=selected_status,
        year=year,
    )

    total = len(review_rows)
    page_rows = review_rows[offset : offset + limit]
    export_query = urlencode(
        {
            "district": district or "",
            "status": selected_status,
            "year": year,
        }
    )

    return templates.TemplateResponse(
        request,
        "mapping_review.html",
        {
            "request": request,
            "districts": districts,
            "active_district": district or "",
            "status": selected_status,
            "status_options": REVIEW_STATUS_OPTIONS,
            "decision_statuses": MAPPING_DECISION_STATUSES,
            "review_write_enabled": _review_write_enabled(),
            "review_write_token_required": _review_write_token_required(),
            "status_counts": status_counts,
            "year": year,
            "message": message,
            "items": page_rows,
            "total": total,
            "offset": offset,
            "limit": limit,
            "export_query": export_query,
            "mapping_status_badge": mapping_status_badge,
            "disclaimer": DISCLAIMER_TEXT,
        },
    )


@router.post("/review/mappings/{policy_id}/decision")
async def mapping_review_decision(
    policy_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    body = (await request.body()).decode()
    form = parse_qs(body)
    return_year = _form_value(form, "year") or str(DEFAULT_MAPPING_YEAR)
    return_district = _form_value(form, "district")
    return_status = _form_value(form, "status") or "needs_review"
    review_decision = _form_value(form, "review_decision")
    review_notes = _form_value(form, "review_notes")
    current_status = _form_value(form, "current_status")
    reviewed_by = _form_value(form, "reviewed_by") or "web_review"
    submitted_token = _form_value(form, "review_token")

    if not _review_write_enabled():
        raise HTTPException(status_code=403, detail="Review write is disabled")
    if not _review_write_authorized(submitted_token):
        raise HTTPException(status_code=403, detail="Invalid review write token")

    if review_decision not in MAPPING_DECISION_STATUSES:
        return RedirectResponse(
            _review_return_url(
                year=return_year,
                district=return_district,
                status=return_status,
                message="invalid_decision",
            ),
            status_code=303,
        )

    policy = await session.get(EnrollmentPolicy, policy_id)
    if policy is None or policy.policy_type != PolicyType.DISTRICT_MAPPING:
        raise HTTPException(status_code=404, detail="Mapping policy not found")

    old_fields = dict(policy.fields or {})
    db_status = _mapping_status(old_fields)
    if current_status and current_status != db_status:
        return RedirectResponse(
            _review_return_url(
                year=return_year,
                district=return_district,
                status=return_status,
                message="stale",
            ),
            status_code=303,
        )

    new_fields = _reviewed_mapping_fields(
        old_fields,
        review_decision=review_decision,
        review_notes=review_notes,
        reviewed_by=reviewed_by,
    )
    if new_fields != old_fields:
        _add_mapping_review_audit(
            session,
            policy=policy,
            old_fields=old_fields,
            new_fields=new_fields,
        )
        await session.commit()

    return RedirectResponse(
        _review_return_url(
            year=return_year,
            district=return_district,
            status=return_status,
            message="updated",
        ),
        status_code=303,
    )


@router.get("/review/mappings.csv")
async def mapping_review_csv(
    district: str | None = None,
    status: str = Query(default="needs_review"),
    year: int = Query(default=2026, ge=2000, le=2100),
    session: AsyncSession = Depends(get_db_session),
):
    selected_status = status if status in REVIEW_STATUS_OPTIONS else "needs_review"
    review_rows, _status_counts = await _mapping_review_rows(
        session,
        district=district,
        selected_status=selected_status,
        year=year,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "district_code",
            "district_name",
            "school_id",
            "school_name",
            "year",
            "mapping_status",
            "enrollment_scope",
            "source_page",
            "reference_year",
            "framework_year",
            "notes",
            "review_decision",
            "review_notes",
        ]
    )
    for item in review_rows:
        fields = item["fields"]
        writer.writerow(
            [
                item["district"].code,
                item["district"].name,
                item["school"].id,
                item["school"].name,
                item["policy"].year,
                item["status"],
                fields.get("enrollment_scope", ""),
                fields.get("source_page", ""),
                fields.get("reference_year", ""),
                fields.get("framework_year", ""),
                fields.get("notes", ""),
                "",
                "",
            ]
        )

    filename = f"mapping-review-{year}-{selected_status}.csv"
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/schools/{school_id}")
async def school_detail_page(
    request: Request,
    school_id: UUID,
    year: int = Query(default=DEFAULT_MAPPING_YEAR, ge=2000, le=2100),
    session: AsyncSession = Depends(get_db_session),
):
    repo = PolicyRepository(session)
    data = await repo.get_school_with_policies(school_id)
    if data is None:
        raise HTTPException(status_code=404, detail="School not found")

    district = await session.get(District, data.school.district_id)
    enrollment, enrollment_is_district = await resolve_school_enrollment_policies(
        session,
        district_id=data.school.district_id,
        school_policies=data.enrollment_policies,
        year=year,
    )
    promotion = await build_promotion_policy_outs(
        session, [p for p in data.promotion_policies if p.year == year]
    )
    available_years = await _load_school_mapping_years(session, school_id)
    if year not in available_years:
        available_years = [year, *available_years]

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

    mapping_policy = next(
        (p for p in enrollment if p.policy_type == PolicyType.DISTRICT_MAPPING),
        None,
    )
    mapping_fields = mapping_policy.fields if mapping_policy else {}
    mapping_badge = mapping_status_badge(mapping_fields.get("mapping_status"))

    return templates.TemplateResponse(
        request,
        "school_detail.html",
        {
            "request": request,
            "school": data.school,
            "district": district,
            "enrollment_policies": enrollment,
            "enrollment_is_district": enrollment_is_district,
            "promotion_policies": promotion,
            "mapping_policy": mapping_policy,
            "mapping_badge": mapping_badge,
            "mapping_provenance": mapping_provenance_lines(mapping_fields),
            "year": year,
            "available_years": available_years,
            "field_labels": POLICY_FIELD_LABELS,
            "policy_type_labels": POLICY_TYPE_LABELS,
            "changes": changes,
            "school_type_labels": SCHOOL_TYPE_LABELS,
            "school_level_labels": SCHOOL_LEVEL_LABELS,
            "disclaimer": DISCLAIMER_TEXT,
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
        request,
        "gov_policies.html",
        {
            "request": request,
            "districts": districts,
            "active_district": active_district,
            "policies": items,
            "total": total,
            "year": year,
            "field_labels": POLICY_FIELD_LABELS,
            "policy_type_labels": POLICY_TYPE_LABELS,
        },
    )
