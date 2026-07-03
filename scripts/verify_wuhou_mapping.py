"""W1.4 武侯划片验收：dry-run 覆盖 + 可选 DB 核对。"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

from chengdu_edu_core.school_names import match_school_name
from chengdu_edu_storage.db import SessionLocal

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from import_district_mapping_policies import (  # noqa: E402
    _is_valid_scope,
    _resolve_override_row,
    load_framework_year,
    load_mapping_overrides,
    load_school_aliases,
    load_scraped,
)
from chengdu_edu_parsers.mapping_parser import merge_scope_dicts

PENDING_YAML = ROOT / "configs" / "districts" / "wuhou" / "mapping_pending.yaml"


def dry_run_coverage(district_code: str = "wuhou") -> dict:
    scraped = load_scraped(district_code) or {}
    scopes = merge_scope_dicts(
        (scraped.get("school_scopes") or []) + load_mapping_overrides(district_code)
    )
    aliases = load_school_aliases(district_code)
    schools_path = ROOT / "configs" / "districts" / district_code / "schools.yaml"
    schools = yaml.safe_load(schools_path.read_text(encoding="utf-8"))["schools"]
    public_primary = [
        s["name"]
        for s in schools
        if s.get("type") == "public" and s.get("level") in ("primary", "nine_year")
    ]
    known = [s["name"] for s in schools if s.get("level") in ("primary", "nine_year", "middle")]

    best: dict[str, dict] = {}
    unmatched = 0
    for row in scopes:
        scope_text = row.get("enrollment_scope", "")
        if not _is_valid_scope(scope_text):
            continue
        db_name = match_school_name(row.get("school_name", ""), known, aliases=aliases)
        if not db_name:
            unmatched += 1
            continue
        best[db_name] = row

    for override in load_mapping_overrides(district_code):
        resolved = _resolve_override_row(override, best, known, aliases)
        if resolved and _is_valid_scope(resolved.get("enrollment_scope", "")):
            best[resolved["db_name"]] = resolved

    # Build canonical name set for pending check (resolves aliases)
    canonical_public_primary = set()
    for name in public_primary:
        canonical = match_school_name(name, known, aliases=aliases)
        canonical_public_primary.add(canonical or name)

    pending = [n for n in public_primary if (match_school_name(n, known, aliases=aliases) or n) not in best]
    without_source = [
        n
        for n, row in best.items()
        if not (row.get("source_url") or row.get("source_page"))
    ]

    return {
        "mapped": len(best),
        "unmatched_scope_names": unmatched,
        "pending_public_primary": pending,
        "without_source_page": without_source,
        "framework_year": load_framework_year(district_code),
    }


async def db_status(year: int = 2025) -> dict:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT ep.fields->>'mapping_status' AS status, COUNT(*)::int AS cnt
                    FROM enrollment_policies ep
                    JOIN districts d ON d.id = ep.district_id
                    WHERE d.code = 'wuhou'
                      AND ep.policy_type = 'district_mapping'
                      AND ep.year = :year
                    GROUP BY 1
                    ORDER BY 1
                    """
                ),
                {"year": year},
            )
        ).all()
        pending = (
            await session.execute(
                text(
                    """
                    SELECT COUNT(*)::int
                    FROM enrollment_policies ep
                    JOIN districts d ON d.id = ep.district_id
                    JOIN schools s ON s.id = ep.school_id
                    WHERE d.code = 'wuhou'
                      AND ep.policy_type = 'district_mapping'
                      AND ep.year = :year
                      AND ep.fields->>'mapping_status' = 'pending_official'
                      AND s.type = 'public'
                    """
                ),
                {"year": year},
            )
        ).scalar_one()
    return {"by_status": {r.status: r.cnt for r in rows}, "pending_public": pending}


def main() -> int:
    parser = argparse.ArgumentParser(description="Wuhou district_mapping acceptance (W1.4)")
    parser.add_argument("--db", action="store_true", help="also query PostgreSQL")
    args = parser.parse_args()

    dry = dry_run_coverage()
    print("=== dry-run ===")
    print(json.dumps(dry, ensure_ascii=False, indent=2))

    ok = dry["unmatched_scope_names"] == 0 and len(dry["pending_public_primary"]) == 0

    if args.db:
        try:
            db = asyncio.run(db_status(dry["framework_year"]))
            print("=== database ===")
            print(json.dumps(db, ensure_ascii=False, indent=2))
            ok = ok and db["pending_public"] <= 3
        except Exception as exc:
            print(f"database check skipped: {exc}", file=sys.stderr)
            ok = False

    if PENDING_YAML.is_file():
        pending_cfg = yaml.safe_load(PENDING_YAML.read_text(encoding="utf-8"))
        done = sum(1 for s in pending_cfg.get("schools", []) if s.get("status") == "done")
        total = pending_cfg.get("summary", {}).get("total", 0)
        print(f"pending_yaml: {done}/{total} done")

    print("W1.4 acceptance:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
