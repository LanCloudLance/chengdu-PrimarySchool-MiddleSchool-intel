"""划片状态徽章与来源链展示（W3 门户）。"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.enums import PolicyType
from chengdu_edu_storage.orm import EnrollmentPolicy

DISCLAIMER_TEXT = (
    "本站信息摘自本地宝等公开转载及区教育局公告整理，仅供参考，"
    "不作为入学依据。划片范围、对口初中以武侯区教育局当年公布文件及"
    "成都市义务教育招生入学服务平台（yjrx）为准。"
)

MAPPING_STATUS_META: dict[str, dict[str, str]] = {
    "verified": {
        "label": "已核实",
        "badge_class": "bg-green-100 text-green-800 border-green-200",
    },
    "reference": {
        "label": "参考",
        "badge_class": "bg-blue-100 text-blue-800 border-blue-200",
    },
    "pending_official": {
        "label": "待官方",
        "badge_class": "bg-amber-100 text-amber-800 border-amber-200",
    },
}


def mapping_status_badge(status: str | None) -> dict[str, str] | None:
    if not status:
        return None
    meta = MAPPING_STATUS_META.get(status)
    if meta:
        return meta
    return {
        "label": status,
        "badge_class": "bg-gray-100 text-gray-700 border-gray-200",
    }


def mapping_provenance_lines(fields: dict) -> list[tuple[str, str]]:
    """来源链：framework_year / reference_year / source_page。"""
    lines: list[tuple[str, str]] = []
    if fields.get("framework_year"):
        lines.append(("框架年份", str(fields["framework_year"])))
    if fields.get("reference_year"):
        lines.append(("划片参考年", str(fields["reference_year"])))
    if fields.get("source_page"):
        lines.append(("来源页面", str(fields["source_page"])))
    return lines


async def batch_district_mapping_summaries(
    session: AsyncSession,
    school_ids: list[UUID],
) -> dict[UUID, dict]:
    if not school_ids:
        return {}
    stmt = (
        select(EnrollmentPolicy)
        .where(
            EnrollmentPolicy.school_id.in_(school_ids),
            EnrollmentPolicy.policy_type == PolicyType.DISTRICT_MAPPING,
        )
        .order_by(EnrollmentPolicy.year.desc())
    )
    rows = list((await session.execute(stmt)).scalars().all())
    out: dict[UUID, dict] = {}
    for policy in rows:
        sid = policy.school_id
        if sid is None or sid in out:
            continue
        out[sid] = dict(policy.fields or {})
    return out
