"""从区级 gov_policy 原文解析小升初规则，写入各校 promotion_policies。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from chengdu_edu_parsers.rule_parser import RuleParser
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import (
    DataSource,
    District,
    EnrollmentPolicy,
    RawDocument,
    School,
)
from chengdu_edu_storage.repository import PolicyRepository
from chengdu_edu_core.enums import PolicyType

ROOT = Path(__file__).resolve().parent.parent
PROMOTION_RULES = ROOT / "configs" / "source_rules" / "_gov_promotion_common.yaml"
CORE_DISTRICTS = (
    "jinjiang",
    "qingyang",
    "wuhou",
    "chenghua",
    "jinniu",
    "gaoxin",
    "tianfu",
)


async def load_gov_policy_text(session, district_code: str) -> tuple[str, int, RawDocument | None]:
    stmt = (
        select(EnrollmentPolicy, RawDocument)
        .join(District, EnrollmentPolicy.district_id == District.id)
        .outerjoin(RawDocument, RawDocument.id == EnrollmentPolicy.source_doc_id)
        .where(
            District.code == district_code,
            EnrollmentPolicy.school_id.is_(None),
            EnrollmentPolicy.policy_type == PolicyType.GOV_POLICY,
        )
        .order_by(EnrollmentPolicy.year.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        return "", 2026, None
    policy, doc = row
    text = (doc.raw_content if doc and doc.raw_content else "") or ""
    return text, policy.year, doc


async def get_or_create_promotion_doc(session, district_code: str) -> RawDocument:
    stmt = (
        select(DataSource)
        .join(District, DataSource.district_id == District.id)
        .where(District.code == district_code, DataSource.is_active.is_(True))
        .limit(1)
    )
    source = (await session.execute(stmt)).scalar_one_or_none()
    if source is None:
        raise ValueError(f"no active source for {district_code}")

    content_hash = f"promotion-{district_code}-gov-derived"
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
        raw_content=f"Derived promotion rules for {district_code}",
        raw_file_path=str(PROMOTION_RULES),
        fetched_at=datetime.now(timezone.utc),
        http_status=200,
    )
    session.add(doc)
    await session.flush()
    return doc


async def import_district_promotion(district_code: str) -> int:
    rules = yaml.safe_load(PROMOTION_RULES.read_text(encoding="utf-8"))
    parser = RuleParser()

    async with SessionLocal() as session:
        text, year, gov_doc = await load_gov_policy_text(session, district_code)
        if not text or len(text) < 500:
            print(f"  skip {district_code}: no gov policy raw text")
            return 0

        parsed = parser.parse_content(text, rules, year=year)
        fields = {k: v for k, v in parsed.fields.items() if v}
        if not fields:
            print(f"  skip {district_code}: no promotion fields parsed")
            return 0

        fields["notes"] = "区级小升初通用规则（摘自本区招生政策，非本校对口明细）"
        if gov_doc:
            fields["source_doc"] = gov_doc.raw_file_path or "gov_policy"

        district_id = (
            await session.execute(
                select(District.id).where(District.code == district_code)
            )
        ).scalar_one()
        doc = gov_doc or await get_or_create_promotion_doc(session, district_code)
        await session.commit()

        schools = list(
            (
                await session.execute(
                    select(School).where(School.district_id == district_id)
                )
            ).scalars().all()
        )
        policy_repo = PolicyRepository(session)
        count = 0
        for school in schools:
            existing_id = await policy_repo.find_promotion_id(
                district_id=district_id, school_id=school.id, year=year
            )
            await policy_repo.upsert_promotion(
                district_id=district_id,
                school_id=school.id,
                year=year,
                fields=fields,
                source_doc_id=doc.id,
                existing_id=existing_id,
            )
            count += 1
        return count


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    args = parser.parse_args()

    targets = CORE_DISTRICTS if args.all_core else (args.districts or ["wuhou"])
    total = 0
    for code in targets:
        n = await import_district_promotion(code)
        print(f"imported promotion policies: {n} ({code})")
        total += n
    print(f"total promotion rows: {total}")


if __name__ == "__main__":
    asyncio.run(main())
