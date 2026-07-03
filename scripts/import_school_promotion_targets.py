"""解析对口初中关系，更新 promotion_policies.target_school_id 与 fields。"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

from chengdu_edu_core.enums import SchoolLevel
from chengdu_edu_core.school_names import match_school_name
from chengdu_edu_parsers.mapping_parser import PromotionLink, infer_group_promotion_links, merge_promotion_links
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import DataSource, District, PromotionPolicy, RawDocument, School
from chengdu_edu_storage.repository import PolicyRepository

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


def load_school_aliases(district_code: str) -> dict[str, str]:
    path = ROOT / "configs" / "districts" / district_code / "school_aliases.yaml"
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return dict(data.get("aliases") or {})


def load_promotion_inference(district_code: str) -> set[str]:
    path = ROOT / "configs" / "districts" / district_code / "promotion_inference.yaml"
    if not path.is_file():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return set(data.get("allow_tokens") or [])


def _apply_alias(name: str, aliases: dict[str, str]) -> str:
    return aliases.get(name, name)


def _infer_token(primary_name: str) -> str | None:
    cleaned = re.sub(r"(四川省|四川|成都市|成都)", "", primary_name)
    for suffix in (
        "附属实验小学",
        "附属小学",
        "实验学校",
        "实验小学",
        "外国语学校",
        "小学",
        "中学",
    ):
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)]
            break
    cleaned = cleaned.strip()
    return cleaned if len(cleaned) >= 2 else None


def filter_inferred_links(
    links: list[PromotionLink],
    *,
    allow_tokens: set[str],
    nine_year_names: set[str],
) -> list[PromotionLink]:
    kept: list[PromotionLink] = []
    for link in links:
        if not link.source_excerpt.startswith("品牌词推断"):
            kept.append(link)
            continue
        if link.primary_name in nine_year_names:
            continue
        tok = _infer_token(link.primary_name)
        if tok and tok in allow_tokens:
            kept.append(link)
    return kept


def load_promotion_links(district_code: str) -> list[PromotionLink]:
    path = ROOT / "configs" / "districts" / district_code / "mapping_scraped.json"
    links: list[PromotionLink] = []
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        for row in data.get("promotion_links") or []:
            links.append(
                PromotionLink(
                    primary_name=row["primary_name"],
                    target_names=row.get("target_names") or [],
                    promotion_type=row.get("promotion_type", "对口直升"),
                    source_excerpt=row.get("source_excerpt", ""),
                )
            )
    return links


def build_promotion_links(
    district_code: str,
    primary_names: list[str],
    middle_names: list[str],
    *,
    nine_year_names: set[str] | None = None,
) -> list[PromotionLink]:
    aliases = load_school_aliases(district_code)
    allow_tokens = load_promotion_inference(district_code)
    nine_year = nine_year_names or set()

    links = load_promotion_links(district_code)
    for row in links:
        row.primary_name = _apply_alias(row.primary_name, aliases)
        row.target_names = [_apply_alias(t, aliases) for t in row.target_names]

    inferred = infer_group_promotion_links(primary_names, middle_names)
    if allow_tokens:
        inferred = filter_inferred_links(
            inferred, allow_tokens=allow_tokens, nine_year_names=nine_year
        )
    links.extend(inferred)

    for name in nine_year:
        links.append(
            PromotionLink(
                primary_name=name,
                target_names=[name],
                promotion_type="一贯制直升",
                source_excerpt="九年一贯制学校校内直升",
            )
        )

    return merge_promotion_links(links)


async def import_district_promotion_targets(district_code: str) -> tuple[int, int]:
    async with SessionLocal() as session:
        district_id = (
            await session.execute(
                select(District.id).where(District.code == district_code)
            )
        ).scalar_one()

        schools = list(
            (
                await session.execute(select(School).where(School.district_id == district_id))
            ).scalars().all()
        )
        if not schools:
            return 0, 0

        aliases = load_school_aliases(district_code)
        primaries = [s for s in schools if s.level in (SchoolLevel.PRIMARY, SchoolLevel.NINE_YEAR)]
        middles = [s for s in schools if s.level in (SchoolLevel.MIDDLE, SchoolLevel.NINE_YEAR)]
        primary_names = [s.name for s in primaries]
        middle_names = [s.name for s in middles]
        name_to_id = {s.name: s.id for s in schools}

        # 九年一贯制：校内直升（优先于品牌推断）
        deduped: dict[str, PromotionLink] = {}
        for school in schools:
            if school.level == SchoolLevel.NINE_YEAR:
                deduped[school.name] = PromotionLink(
                    primary_name=school.name,
                    target_names=[school.name],
                    promotion_type="一贯制直升",
                    source_excerpt="九年一贯制学校校内直升",
                )

        nine_year_names = {s.name for s in schools if s.level == SchoolLevel.NINE_YEAR}
        for link in build_promotion_links(
            district_code, primary_names, middle_names, nine_year_names=nine_year_names
        ):
            deduped[link.primary_name] = link

        policy_repo = PolicyRepository(session)
        year = 2026
        updated = 0
        skipped = 0

        source = (
            await session.execute(
                select(DataSource)
                .join(District, DataSource.district_id == District.id)
                .where(District.code == district_code, DataSource.is_active.is_(True))
                .limit(1)
            )
        ).scalar_one_or_none()

        doc: RawDocument | None = None
        if source:
            content_hash = f"promotion-targets-{district_code}"
            doc = (
                await session.execute(
                    select(RawDocument).where(
                        RawDocument.source_id == source.id,
                        RawDocument.content_hash == content_hash,
                    )
                )
            ).scalar_one_or_none()
            if doc is None:
                doc = RawDocument(
                    source_id=source.id,
                    content_hash=content_hash,
                    raw_content=f"Promotion target links for {district_code}",
                    raw_file_path=str(
                        ROOT / "configs" / "districts" / district_code / "mapping_scraped.json"
                    ),
                    fetched_at=datetime.now(timezone.utc),
                    http_status=200,
                )
                session.add(doc)
                await session.flush()
            await session.commit()

        linked_primaries = set(deduped.keys())

        for school in primaries:
            if school.name in linked_primaries:
                continue
            existing_id = await policy_repo.find_promotion_id(
                district_id=district_id, school_id=school.id, year=year
            )
            if not existing_id:
                continue
            policy = await session.get(PromotionPolicy, existing_id)
            if policy is None or policy.target_school_id is None:
                continue
            fields = dict(policy.fields or {})
            if not str(fields.get("target_source", "")).startswith("品牌词推断"):
                continue
            fields.pop("target_schools", None)
            fields.pop("promotion_type", None)
            fields.pop("target_source", None)
            policy.target_school_id = None
            await policy_repo.upsert_promotion(
                district_id=district_id,
                school_id=school.id,
                year=year,
                fields=fields,
                source_doc_id=policy.source_doc_id or doc.id,
                target_school_id=None,
                existing_id=existing_id,
            )

        for primary_name, link in deduped.items():
            lookup_primary = _apply_alias(link.primary_name, aliases)
            primary_id_name = match_school_name(lookup_primary, primary_names)
            if not primary_id_name:
                skipped += 1
                continue

            resolved_targets: list[str] = []
            for target in link.target_names:
                lookup_target = _apply_alias(target, aliases)
                matched = match_school_name(lookup_target, middle_names + primary_names)
                if matched and matched not in resolved_targets:
                    resolved_targets.append(matched)

            if not resolved_targets:
                skipped += 1
                continue

            school_id = name_to_id[primary_id_name]
            target_school_id = name_to_id.get(resolved_targets[0])

            existing_id = await policy_repo.find_promotion_id(
                district_id=district_id, school_id=school_id, year=year
            )
            if existing_id:
                policy = await session.get(PromotionPolicy, existing_id)
                fields = dict(policy.fields) if policy else {}
            else:
                fields = {}

            fields["promotion_type"] = link.promotion_type
            fields["target_schools"] = resolved_targets
            if link.source_excerpt:
                fields["target_source"] = link.source_excerpt[:300]
            fields["notes"] = fields.get("notes") or "对口关系（自动解析/推断，请核对当年官方文件）"

            if doc is None:
                skipped += 1
                continue

            await policy_repo.upsert_promotion(
                district_id=district_id,
                school_id=school_id,
                year=year,
                fields=fields,
                source_doc_id=doc.id,
                target_school_id=target_school_id,
                existing_id=existing_id,
            )
            updated += 1

    return updated, skipped


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    args = parser.parse_args()

    targets = CORE_DISTRICTS if args.all_core else (args.districts or CORE_DISTRICTS)
    total_u = total_s = 0
    for code in targets:
        updated, skipped = await import_district_promotion_targets(code)
        print(f"updated promotion targets: {updated} updated, {skipped} skipped ({code})")
        total_u += updated
        total_s += skipped
    print(f"total promotion target updates: {total_u}")


if __name__ == "__main__":
    asyncio.run(main())
