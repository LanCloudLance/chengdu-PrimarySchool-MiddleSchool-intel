"""W2.4 武侯对口升学验收：dry-run 覆盖 + 可选 DB 核对。"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

from chengdu_edu_core.enums import SchoolLevel
from chengdu_edu_core.school_names import match_school_name
from chengdu_edu_storage.db import SessionLocal

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_school_promotion_targets import (  # noqa: E402
    build_promotion_links,
    load_school_aliases,
)

COVERAGE_TARGET = 0.60


def dry_run_coverage(district_code: str = "wuhou") -> dict:
    schools_path = ROOT / "configs" / "districts" / district_code / "schools.yaml"
    schools = yaml.safe_load(schools_path.read_text(encoding="utf-8"))["schools"]
    aliases = load_school_aliases(district_code)

    public_primary = [
        s["name"]
        for s in schools
        if s.get("type") == "public" and s.get("level") in ("primary", "nine_year")
    ]
    middle_names = [
        s["name"]
        for s in schools
        if s.get("level") in ("middle", "nine_year")
    ]
    nine_year = {s["name"] for s in schools if s.get("level") == "nine_year"}

    links = build_promotion_links(
        district_code, public_primary, middle_names, nine_year_names=nine_year
    )
    link_map = {link.primary_name: link for link in links}

    covered: list[str] = []
    uncovered: list[str] = []
    lottery: list[str] = []

    for name in public_primary:
        lookup = aliases.get(name, name)
        matched = match_school_name(lookup, list(link_map.keys())) or (
            name if name in link_map else None
        )
        if not matched:
            uncovered.append(name)
            continue
        link = link_map.get(matched) or link_map.get(name)
        if link is None:
            uncovered.append(name)
            continue
        covered.append(name)
        if "多校" in link.promotion_type or "摇号" in link.promotion_type:
            lottery.append(name)

    scraped_path = ROOT / "configs" / "districts" / district_code / "mapping_scraped.json"
    promo_rows = 0
    if scraped_path.is_file():
        promo_rows = len(
            json.loads(scraped_path.read_text(encoding="utf-8")).get("promotion_links") or []
        )

    rate = len(covered) / len(public_primary) if public_primary else 0.0
    return {
        "public_primary": len(public_primary),
        "covered": len(covered),
        "coverage_rate": round(rate, 3),
        "lottery_or_multi": len(lottery),
        "uncovered": uncovered,
        "promotion_links_scraped": promo_rows,
        "inferred_total": len(links),
    }


async def db_coverage(district_code: str = "wuhou", year: int = 2026) -> dict:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT s.name, s.level::text, pp.target_school_id,
                           pp.fields->>'promotion_type' AS promo_type,
                           pp.fields->>'target_schools' AS targets
                    FROM promotion_policies pp
                    JOIN schools s ON s.id = pp.school_id
                    JOIN districts d ON d.id = pp.district_id
                    WHERE d.code = :code AND pp.year = :year
                    ORDER BY s.name
                    """
                ),
                {"code": district_code, "year": year},
            )
        ).mappings().all()

    public_primary = [
        r
        for r in rows
        if r["level"] in (SchoolLevel.PRIMARY.value, SchoolLevel.NINE_YEAR.value)
        and r["name"]
    ]
    # filter public - need join with schools.type; simplify via dry-run list
    with_target = [r for r in rows if r["target_school_id"] or r["targets"]]
    return {
        "promotion_rows": len(rows),
        "with_target_fk_or_fields": len(with_target),
        "sample": [dict(r) for r in with_target[:5]],
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description="Wuhou promotion acceptance (W2.4)")
    parser.add_argument("--db", action="store_true", help="Also query promotion_policies")
    args = parser.parse_args()

    stats = dry_run_coverage()
    print("=== dry-run ===")
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    ok = stats["coverage_rate"] >= COVERAGE_TARGET and stats["promotion_links_scraped"] > 0

    if args.db:
        db_stats = await db_coverage()
        print("=== db ===")
        print(json.dumps(db_stats, ensure_ascii=False, indent=2, default=str))

    print("W2.4 acceptance:", "PASS" if ok else "FAIL")
    if not ok:
        print(f"  need coverage >= {COVERAGE_TARGET:.0%}, scraped promotion_links > 0")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
