"""七区划片/inventory 批量验收（武侯另跑 verify_wuhou_all）。"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from verify_wuhou_mapping import dry_run_coverage  # noqa: E402

CORE = ("jinjiang", "qingyang", "wuhou", "chenghua", "jinniu", "gaoxin", "tianfu")
MIN_SCOPES = {
    "wuhou": 40,
    "jinjiang": 15,
    "qingyang": 15,
    "chenghua": 15,
    "gaoxin": 3,
    "tianfu": 20,
    "jinniu": 0,
}
MIN_INVENTORY = {
    "wuhou": 90,
    "jinjiang": 20,
    "qingyang": 8,
    "chenghua": 8,
    "jinniu": 7,
    "gaoxin": 8,
    "tianfu": 8,
}


def inventory_count(code: str) -> int:
    path = ROOT / "configs" / "districts" / code / "schools.yaml"
    if not path.is_file():
        return 0
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return len(doc.get("schools") or [])


def scraped_scope_count(code: str) -> int:
    path = ROOT / "configs" / "districts" / code / "mapping_scraped.json"
    if not path.is_file():
        return 0
    doc = json.loads(path.read_text(encoding="utf-8"))
    return len(doc.get("school_scopes") or [])


def check_district_local(code: str) -> tuple[bool, str, dict]:
    """Filesystem checks only; returns (ok, msg, context for db pass)."""
    inv = inventory_count(code)
    scopes = scraped_scope_count(code)
    min_inv = MIN_INVENTORY.get(code, 5)
    min_scopes = MIN_SCOPES.get(code, 1)
    ctx = {"inv": inv, "scopes": scopes, "min_inv": min_inv}

    if inv < min_inv:
        return False, f"inventory {inv} < {min_inv}", ctx

    if min_scopes > 0 and scopes < min_scopes:
        return False, f"scopes {scopes} < {min_scopes}", ctx

    if scopes > 0:
        cov = dry_run_coverage(code)
        if cov["unmatched_scope_names"] > 0:
            return False, f"unmatched {cov['unmatched_scope_names']}", ctx
        if code == "wuhou" and len(cov["pending_public_primary"]) > 3:
            return False, f"pending {len(cov['pending_public_primary'])}", ctx

    return True, f"inv={inv} scopes={scopes}", ctx


async def db_mapping_counts_all(codes: tuple[str, ...], year: int = 2025) -> dict[str, dict]:
    from chengdu_edu_storage.db import SessionLocal

    out: dict[str, dict] = {}
    async with SessionLocal() as session:
        for code in codes:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) AS total,
                               COUNT(*) FILTER (
                                 WHERE ep.fields->>'mapping_status' != 'pending_official'
                               ) AS mapped
                        FROM enrollment_policies ep
                        JOIN districts d ON d.id = ep.district_id
                        WHERE d.code = :code
                          AND ep.policy_type = 'district_mapping'
                          AND ep.year = :year
                          AND ep.school_id IS NOT NULL
                        """
                    ),
                    {"code": code, "year": year},
                )
            ).mappings().first()
            intel = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM intel_entries ie
                        JOIN districts d ON d.id = ie.district_id
                        WHERE d.code = :code AND ie.intel_type = 'mapping'
                        """
                    ),
                    {"code": code},
                )
            ).scalar_one()
            out[code] = {
                "policies": int(row["total"] or 0),
                "mapped_non_pending": int(row["mapped"] or 0),
                "intel_mapping": int(intel or 0),
            }
    return out


def check_district_db(code: str, ctx: dict, db: dict) -> tuple[bool, str]:
    min_inv = ctx["min_inv"]
    inv = ctx["inv"]
    scopes = ctx["scopes"]
    if db["policies"] < min_inv // 2 and code != "jinniu":
        return False, f"db policies {db['policies']}"
    return True, f"inv={inv} scopes={scopes} db={db}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify all 7 core districts")
    parser.add_argument("--db", action="store_true")
    args = parser.parse_args()

    failed: list[str] = []
    print("=== verify_all_districts ===")

    local: dict[str, tuple[bool, str, dict]] = {}
    for code in CORE:
        ok, msg, ctx = check_district_local(code)
        local[code] = (ok, msg, ctx)
        if not ok:
            failed.append(code)

    db_counts: dict[str, dict] = {}
    if args.db:
        db_counts = asyncio.run(db_mapping_counts_all(CORE))

    for code in CORE:
        ok, msg, ctx = local[code]
        if ok and args.db:
            ok, msg = check_district_db(code, ctx, db_counts[code])
            if not ok and code not in failed:
                failed.append(code)
        status = "PASS" if ok else "FAIL"
        print(f"{code}: {status} ({msg})")

    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL DISTRICTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
