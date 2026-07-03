"""从 inventory YAML 导入校级别招生登记信息（SCHOOL_ENROLLMENT）。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from chengdu_edu_core.enums import PolicyType
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import DataSource, District, EnrollmentPolicy, RawDocument
from chengdu_edu_storage.repository import PolicyRepository
from chengdu_edu_storage.school_repository import SchoolRepository

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from import_schools import load_all_school_configs, load_schools_config  # noqa: E402

DISTRICT_YAML = "configs/districts/{code}/schools.yaml"


def district_school_rows(district_code: str) -> list[dict]:
    path = ROOT / DISTRICT_YAML.format(code=district_code)
    if path.is_file():
        return load_schools_config(path)
    return [s for s in load_all_school_configs() if s.get("district_code") == district_code]


async def district_gov_registration_time(
    session, district_id
) -> str | None:
    stmt = (
        select(EnrollmentPolicy)
        .where(
            EnrollmentPolicy.district_id == district_id,
            EnrollmentPolicy.school_id.is_(None),
            EnrollmentPolicy.policy_type == PolicyType.GOV_POLICY,
        )
        .order_by(EnrollmentPolicy.year.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row and isinstance(row.fields, dict):
        return row.fields.get("registration_time")
    return None


def build_school_fields(row: dict, *, registration_time: str | None) -> dict:
    fields: dict[str, str] = {}
    if row.get("address"):
        fields["registration_point_address"] = row["address"]
    if row.get("phone"):
        fields["contact_phone"] = row["phone"]
    urls = row.get("source_urls") or {}
    if urls.get("contact_channel"):
        fields["contact_channel"] = urls["contact_channel"]
    if urls.get("verification_url"):
        fields["source_page"] = urls["verification_url"]
    if row.get("enrichment_note"):
        fields["notes"] = row["enrichment_note"]
    if row.get("role"):
        fields["role"] = row["role"]
    if row.get("verification_source"):
        fields["registration_guide"] = row["verification_source"]
    if registration_time:
        fields["registration_time"] = registration_time
    return fields


async def get_or_create_inventory_doc(session, district_code: str) -> RawDocument:
    stmt = (
        select(DataSource)
        .join(District, DataSource.district_id == District.id)
        .where(District.code == district_code, DataSource.is_active.is_(True))
        .limit(1)
    )
    source = (await session.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise ValueError(f"no active data source for district {district_code}")

    content_hash = f"inventory-{district_code}-school-enrollment"
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
        raw_content=f"Imported from {DISTRICT_YAML.format(code=district_code)}",
        raw_file_path=DISTRICT_YAML.format(code=district_code),
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
    )
    session.add(doc)
    await session.flush()
    return doc


async def import_district_school_enrollments(district_code: str) -> int:
    rows = district_school_rows(district_code)
    if not rows:
        return 0

    async with SessionLocal() as session:
        school_repo = SchoolRepository(session)
        policy_repo = PolicyRepository(session)
        districts = await school_repo.get_district_code_map()
        district_id = districts[district_code]
        reg_time = await district_gov_registration_time(session, district_id)
        year = rows[0].get("data_year", 2026)
        doc = await get_or_create_inventory_doc(session, district_code)
        await session.commit()
        count = 0

        for row in rows:
            school_id = await school_repo.find_school_id(
                district_id=district_id, name=row["name"]
            )
            if not school_id:
                continue
            fields = build_school_fields(row, registration_time=reg_time)
            if not fields:
                continue
            existing_id = await policy_repo.find_enrollment_id(
                district_id=district_id,
                school_id=school_id,
                policy_type=PolicyType.SCHOOL_ENROLLMENT,
                year=year,
            )
            await policy_repo.upsert_enrollment(
                district_id=district_id,
                school_id=school_id,
                policy_type=PolicyType.SCHOOL_ENROLLMENT,
                year=year,
                fields=fields,
                source_doc_id=doc.id,
                confidence=0.85,
                existing_id=existing_id,
            )
            count += 1

    return count


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", default="wuhou")
    args = parser.parse_args()
    count = await import_district_school_enrollments(args.district)
    print(f"imported school enrollment policies: {count} ({args.district})")


if __name__ == "__main__":
    asyncio.run(main())
