"""W4 运营化验收：mirror intel、登记点、锦江复制首遍。"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parent.parent
WUHOU_SCHOOLS = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
WUHOU_MIRRORS = ROOT / "configs" / "districts" / "wuhou" / "scraped_mirrors.json"
WUHOU_MANIFEST = ROOT / "configs" / "districts" / "wuhou" / "mirror_intel_manifest.json"
JINJIANG_SCRAPED = ROOT / "configs" / "districts" / "jinjiang" / "mapping_scraped.json"
JINJIANG_SCHOOLS = ROOT / "configs" / "districts" / "jinjiang" / "schools.yaml"


def check_mirror_scrape() -> tuple[bool, str]:
    if not WUHOU_MIRRORS.is_file():
        return False, "missing scraped_mirrors.json"
    doc = json.loads(WUHOU_MIRRORS.read_text(encoding="utf-8"))
    matched = int(doc.get("matched") or len(doc.get("mirrors") or {}))
    if matched < 50:
        return False, f"mirror matched {matched} < 50"
    return True, f"mirror matched {matched}"


def check_mirror_intel_manifest() -> tuple[bool, str]:
    if not WUHOU_MANIFEST.is_file():
        return False, "missing mirror_intel_manifest.json (run sync_mirror_intel.py)"
    doc = json.loads(WUHOU_MANIFEST.read_text(encoding="utf-8"))
    synced = int(doc.get("synced") or 0)
    skipped = int(doc.get("skipped") or 0)
    processed = int(doc.get("processed") or 0)
    entries = len(doc.get("entries") or [])
    targets = int(doc.get("mirror_targets") or 0)
    min_synced = max(40, int(targets * 0.4)) if targets else 40
    # Idempotent re-runs skip existing rows; count synced+skipped or manifest entries.
    effective = max(synced + skipped, processed, entries)
    if effective < min_synced:
        return False, f"mirror intel effective {effective} < {min_synced} (synced={synced})"
    fetch_errors = len(doc.get("errors") or [])
    return True, f"mirror intel {effective}/{targets} (synced={synced} skipped={skipped}) errors={fetch_errors}"


async def check_mirror_intel_db() -> tuple[bool, str]:
    try:
        from chengdu_edu_core.enums import IntelType
        from chengdu_edu_storage.db import SessionLocal
        from chengdu_edu_storage.orm import District, IntelEntry
    except ImportError as exc:
        return False, f"import error: {exc}"

    try:
        async with SessionLocal() as session:
            district_id = (
                await session.execute(select(District.id).where(District.code == "wuhou"))
            ).scalar_one_or_none()
            if district_id is None:
                return False, "wuhou district missing in DB"
            count = (
                await session.execute(
                    select(func.count())
                    .select_from(IntelEntry)
                    .where(
                        IntelEntry.district_id == district_id,
                        IntelEntry.intel_type == IntelType.MIRROR_PAGE,
                    )
                )
            ).scalar_one()
            if count < 40:
                return False, f"DB mirror_page intel {count} < 40"
            return True, f"DB mirror_page intel {count}"
    except Exception as exc:
        return False, f"DB check failed: {exc}"


def check_registration_points() -> tuple[bool, str]:
    if not WUHOU_SCHOOLS.is_file():
        return False, "missing wuhou schools.yaml"
    doc = yaml.safe_load(WUHOU_SCHOOLS.read_text(encoding="utf-8")) or {}
    schools = doc.get("schools") or []
    reg_points = sum(
        1
        for s in schools
        if s.get("role") == "registration_point"
        and s.get("type") == "public"
        and s.get("level") in ("primary", "nine_year")
    )
    guide = (doc.get("sources") or {}).get("registration_guide")
    if reg_points < 50:
        return False, f"registration_point public primary {reg_points} < 50"
    if not guide:
        return False, "missing sources.registration_guide"
    return True, f"registration_points={reg_points} guide={guide[:48]}..."


def check_jinjiang_copy() -> tuple[bool, str]:
    if not JINJIANG_SCRAPED.is_file():
        return False, "missing jinjiang mapping_scraped.json"
    scraped = json.loads(JINJIANG_SCRAPED.read_text(encoding="utf-8"))
    scopes = len(scraped.get("school_scopes") or [])
    if scopes < 15:
        return False, f"jinjiang scopes {scopes} < 15"
    if not JINJIANG_SCHOOLS.is_file():
        return False, "missing jinjiang schools.yaml"
    schools_doc = yaml.safe_load(JINJIANG_SCHOOLS.read_text(encoding="utf-8")) or {}
    inventory = len(schools_doc.get("schools") or [])
    if inventory < 15:
        return False, f"jinjiang inventory {inventory} < 15"
    return True, f"jinjiang scopes={scopes} inventory={inventory}"


def main() -> int:
    parser = argparse.ArgumentParser(description="W4 operational acceptance")
    parser.add_argument("--db", action="store_true", help="Also verify mirror intel in DB")
    args = parser.parse_args()

    checks = [
        ("W4.1 mirror scrape", check_mirror_scrape()),
        ("W4.1 mirror intel manifest", check_mirror_intel_manifest()),
        ("W4.2 registration points", check_registration_points()),
        ("W4.3 jinjiang copy", check_jinjiang_copy()),
    ]
    if args.db:
        db_ok, db_msg = asyncio.run(check_mirror_intel_db())
        checks.append(("W4.1 mirror intel DB", (db_ok, db_msg)))

    failed: list[str] = []
    print("=== W4 operational checks ===")
    for label, (ok, msg) in checks:
        status = "OK" if ok else "FAIL"
        print(f"{label}: {status} ({msg})")
        if not ok:
            failed.append(label)

    if failed:
        print("W4.4 acceptance: FAIL", ", ".join(failed))
        return 1
    print("W4.4 acceptance: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
