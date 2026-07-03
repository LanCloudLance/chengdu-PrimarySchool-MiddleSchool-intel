"""将 mapping_scraped.json 中的划片范围写入 enrollment_policies (district_mapping)。"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from chengdu_edu_core.enums import IntelType, PolicyType, SchoolLevel
from chengdu_edu_core.school_names import match_school_name
from chengdu_edu_parsers.mapping_parser import merge_scope_dicts
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.intel_repository import IntelRepository
from chengdu_edu_storage.orm import DataSource, District, RawDocument, School
from chengdu_edu_storage.repository import PolicyRepository
from chengdu_edu_storage.school_repository import SchoolRepository

ROOT = Path(__file__).resolve().parent.parent
CORE_DISTRICTS = (
    "jinjiang",
    "qingyang",
    "wuhou",
    "chenghua",
    "jinniu",
    "gaoxin",
    "tianfu",
)


def _scope_quality(scope: str) -> int:
    score = len(scope)
    if re.search(r"[至界路街道巷大道]", scope):
        score += 100
    if re.match(r"^\d+\.\s*$", scope):
        score -= 200
    if "号）" in scope or "号)" in scope:
        score -= 50
    return score


def _scope_rank(row: dict) -> tuple:
    source_order = {"override": 0, "adjustment": 1, "html": 2, "ocr": 3}
    return (
        source_order.get(row.get("scope_source") or "html", 2),
        1 if row.get("is_reference") else 0,
        -int(row.get("intel_year") or 0),
        -_scope_quality(row.get("enrollment_scope", "")),
    )


def _is_valid_scope(scope: str) -> bool:
    if len(scope) < 8:
        return False
    # 允许「1.二环路…」式多段划片描述
    if re.match(r"^\d+\.\s*$", scope):
        return False
    return bool(re.search(r"[至界路街道巷大道区社区苑]", scope))


def load_scraped(
    district_code: str, year_filter: int | None = None
) -> dict | None:
    """加载划片 JSON。

    year_filter 为 None 或 2025 时，读取 mapping_scraped.json（向后兼容）。
    year_filter 为 2026 时，必须读取 mapping_scraped_2026.json，
    避免把 2025 数据误导入为 2026。
    """
    base = ROOT / "configs" / "districts" / district_code
    if year_filter and year_filter >= 2026:
        path = base / "mapping_scraped_2026.json"
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
        raise FileNotFoundError(
            f"missing 2026 mapping file for {district_code}: {path}"
        )
    path = base / "mapping_scraped.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_school_aliases(district_code: str) -> dict[str, str]:
    path = ROOT / "configs" / "districts" / district_code / "school_aliases.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("aliases") or {})


def load_framework_year(district_code: str) -> int:
    sources = ROOT / "configs" / "district_mapping_sources.yaml"
    if not sources.is_file():
        return 2025
    cfg = yaml.safe_load(sources.read_text(encoding="utf-8")) or {}
    return int(cfg.get("data_year", 2025))


def load_mapping_overrides(district_code: str) -> list[dict]:
    path = ROOT / "configs" / "districts" / district_code / "mapping_overrides.yaml"
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rows: list[dict] = []
    for row in data.get("overrides") or []:
        item = dict(row)
        item["scope_source"] = "override"
        rows.append(item)
    return rows


def _resolve_override_row(
    row: dict,
    best_scopes: dict[str, dict],
    known_names: list[str],
    aliases: dict[str, str],
) -> dict | None:
    db_name = match_school_name(row.get("school_name", ""), known_names, aliases=aliases)
    if not db_name:
        return None
    resolved = {**row, "db_name": db_name}
    copy_from = row.get("copy_scope_from")
    if copy_from:
        src_name = match_school_name(copy_from, known_names, aliases=aliases) or copy_from
        src = best_scopes.get(src_name)
        if src:
            resolved["enrollment_scope"] = src.get("enrollment_scope", "")
            resolved.setdefault("source_url", src.get("source_url"))
            resolved.setdefault("source_page", src.get("source_url"))
    resolved.setdefault("source_url", resolved.get("source_page", "mapping_overrides.yaml"))
    return resolved


async def load_scopes_from_intel(
    session, district_id, *, framework_year: int
) -> tuple[list[dict], int, bool]:
    """优先从 intel_entries 读取划片；返回 scopes, policy_year, has_only_reference。"""
    repo = IntelRepository(session)
    entries = await repo.list_district_intel(
        district_id=district_id, intel_type=IntelType.MAPPING
    )
    if not entries:
        return [], framework_year, False

    scopes: list[dict] = []
    for entry in entries:
        for row in entry.structured_fields.get("school_scopes") or []:
            scopes.append(
                {
                    **row,
                    "source_url": row.get("source_url") or entry.source_url,
                    "intel_year": row.get("intel_year") or entry.data_year,
                    "is_reference": row.get("is_reference", entry.is_reference),
                }
            )
    merged = merge_scope_dicts(scopes)
    has_only_reference = all(row.get("is_reference") for row in merged) if merged else False
    return merged, framework_year, has_only_reference


async def get_or_create_mapping_doc(session, district_code: str, source_url: str) -> RawDocument:
    stmt = (
        select(DataSource)
        .join(District, DataSource.district_id == District.id)
        .where(District.code == district_code, DataSource.is_active.is_(True))
        .limit(1)
    )
    source = (await session.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise ValueError(f"no active source for {district_code}")

    content_hash = f"mapping-{district_code}-{hash(source_url) & 0xFFFFFFFF:08x}"
    existing = (
        await session.execute(
            select(RawDocument).where(
                RawDocument.source_id == source.id,
                RawDocument.content_hash == content_hash,
            )
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    doc = RawDocument(
        source_id=source.id,
        content_hash=content_hash,
        raw_content=f"Imported mapping from {source_url}",
        raw_file_path=source_url,
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
    )
    session.add(doc)
    await session.flush()
    return doc


async def import_district_mapping(
    district_code: str, target_year: int | None = None
) -> tuple[int, int]:
    framework_year = load_framework_year(district_code)
    scraped = load_scraped(district_code, year_filter=target_year)
    year = scraped.get("data_year", framework_year) if scraped else framework_year
    scopes = scraped.get("school_scopes") or [] if scraped else []
    has_only_reference = False
    aliases = load_school_aliases(district_code)
    override_rows = load_mapping_overrides(district_code)

    async with SessionLocal() as session:
        school_repo = SchoolRepository(session)
        districts = await school_repo.get_district_code_map()
        district_id = districts[district_code]
        intel_scopes, intel_year, has_only_reference = await load_scopes_from_intel(
            session, district_id, framework_year=framework_year
        )
        if target_year is not None:
            # 显式指定年份时使用对应 scraped 文件，不回退到 intel 表。
            pass
        elif intel_scopes:
            scopes = intel_scopes
            year = intel_year

    scopes = merge_scope_dicts(scopes + override_rows)

    if not scopes:
        print(f"  skip {district_code}: no school scopes in intel/cache")
        return 0, 0
    matched = 0
    unmatched = 0

    async with SessionLocal() as session:
        school_repo = SchoolRepository(session)
        policy_repo = PolicyRepository(session)
        districts = await school_repo.get_district_code_map()
        district_id = districts[district_code]

        schools = list(
            (
                await session.execute(
                    select(School).where(
                        School.district_id == district_id,
                        School.level.in_(
                            [
                                SchoolLevel.PRIMARY,
                                SchoolLevel.NINE_YEAR,
                                SchoolLevel.MIDDLE,
                            ]
                        ),
                    )
                )
            ).scalars().all()
        )
        known_names = [s.name for s in schools]
        name_to_id = {s.name: s.id for s in schools}

        doc_cache: dict[str, RawDocument] = {}
        best_scopes: dict[str, dict] = {}

        for row in scopes:
            scope_text = row.get("enrollment_scope", "")
            if not _is_valid_scope(scope_text):
                continue
            candidate = row.get("school_name", "")
            db_name = match_school_name(candidate, known_names, aliases=aliases)
            if not db_name:
                unmatched += 1
                continue
            prev = best_scopes.get(db_name)
            if prev is None or _scope_rank(row) < _scope_rank(prev):
                best_scopes[db_name] = {**row, "db_name": db_name}

        for override in override_rows:
            resolved = _resolve_override_row(override, best_scopes, known_names, aliases)
            if resolved and _is_valid_scope(resolved.get("enrollment_scope", "")):
                best_scopes[resolved["db_name"]] = resolved

        for db_name, row in best_scopes.items():
            source_url = row.get("source_url", "mapping_scraped.json")
            if source_url not in doc_cache:
                doc_cache[source_url] = await get_or_create_mapping_doc(
                    session, district_code, source_url
                )
                await session.commit()
            doc = doc_cache[source_url]

            row_ref = bool(row.get("is_reference"))
            row_year = int(row.get("intel_year") or year)
            row_source = row.get("scope_source") or ""
            if row.get("mapping_status"):
                mapping_status = row["mapping_status"]
            elif row_source == "ocr_image_needs_review":
                mapping_status = "pending_review"
            elif row_source == "bendibao_text":
                mapping_status = "reference"
            elif row_ref:
                mapping_status = "reference"
            else:
                mapping_status = "verified"
            if row.get("notes"):
                notes = row["notes"]
            elif row_source == "ocr_image_needs_review":
                notes = (
                    f"{row_year}年划片范围（来自图片 OCR，待人工复核；"
                    f"{year}年正式范围以教育局/yjrx 平台为准）"
                )
            elif row_ref:
                notes = (
                    f"参考{row_year}年划片（公开转载；{year}年正式范围以教育局/yjrx 平台为准）"
                )
            else:
                notes = f"{row_year}年划片范围（摘自教育局公告/公开转载）"
            fields = {
                "enrollment_scope": row.get("enrollment_scope", ""),
                "source_page": source_url,
                "mapping_status": mapping_status,
                "reference_year": row_year,
                "framework_year": year,
                "notes": notes,
            }
            if row.get("source_excerpt"):
                fields["source_excerpt"] = row["source_excerpt"][:300]

            school_id = name_to_id[db_name]
            existing_id = await policy_repo.find_enrollment_id(
                district_id=district_id,
                school_id=school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=year,
            )
            await policy_repo.upsert_enrollment(
                district_id=district_id,
                school_id=school_id,
                policy_type=PolicyType.DISTRICT_MAPPING,
                year=year,
                fields=fields,
                source_doc_id=doc.id,
                confidence=0.75,
                existing_id=existing_id,
            )
            matched += 1

        pending = await _fill_pending_primary_mappings(
            session=session,
            policy_repo=policy_repo,
            district_id=district_id,
            district_code=district_code,
            schools=schools,
            name_to_id=name_to_id,
            mapped_names=set(best_scopes.keys()),
            year=year,
            doc_cache=doc_cache,
            has_only_reference=has_only_reference,
        )
        matched += pending

    return matched, unmatched


async def _fill_pending_primary_mappings(
    *,
    session,
    policy_repo: PolicyRepository,
    district_id,
    district_code: str,
    schools: list[School],
    name_to_id: dict,
    mapped_names: set[str],
    year: int,
    doc_cache: dict[str, RawDocument],
    has_only_reference: bool = False,
) -> int:
    """为尚无划片的公办小学写入待公布占位情报（避免详情页空白）。"""
    if not doc_cache:
        doc = await get_or_create_mapping_doc(session, district_code, "intel:pending-mapping")
        await session.commit()
        doc_cache["intel:pending-mapping"] = doc
    doc = next(iter(doc_cache.values()))
    count = 0
    if year >= 2026:
        pending_note = (
            "2026年正式划片范围待6月15日成都市义务教育招生入学服务平台公布"
        )
    elif has_only_reference:
        pending_note = (
            f"{year}年框架：暂无结构化划片数据（一览表为图片或未收录），待后续数据源补全"
        )
    else:
        pending_note = f"{year}年暂无公开划片范围，待后续官方数据源补全"
    for school in schools:
        if school.name in mapped_names:
            continue
        if school.type.value != "public":
            continue
        if school.level not in (SchoolLevel.PRIMARY, SchoolLevel.NINE_YEAR):
            continue
        fields = {
            "mapping_status": "pending_official",
            "reference_year": year,
            "framework_year": year,
            "notes": pending_note,
            "registration_point_address": school.address or "",
        }
        existing_id = await policy_repo.find_enrollment_id(
            district_id=district_id,
            school_id=school.id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=year,
        )
        await policy_repo.upsert_enrollment(
            district_id=district_id,
            school_id=school.id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=year,
            fields=fields,
            source_doc_id=doc.id,
            confidence=0.4,
            existing_id=existing_id,
        )
        count += 1
    return count


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="目标数据年份；指定 2026 时读取 mapping_scraped_2026.json",
    )
    args = parser.parse_args()

    targets = CORE_DISTRICTS if args.all_core else (args.districts or ["gaoxin"])
    total_m = total_u = 0
    for code in targets:
        matched, unmatched = await import_district_mapping(
            code, target_year=args.year
        )
        print(f"imported district_mapping: {matched} matched, {unmatched} unmatched ({code})")
        total_m += matched
        total_u += unmatched
    print(f"total district_mapping rows: {total_m} (unmatched names: {total_u})")


if __name__ == "__main__":
    asyncio.run(main())
