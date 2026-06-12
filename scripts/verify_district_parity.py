"""七区「武侯同级」管线通透验收：filesystem + 可选 DB。"""
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

# 合理 inventory 下限（划片校数 + seed 登记点）
MIN_INVENTORY = {
    "wuhou": 90,
    "jinjiang": 25,
    "qingyang": 32,
    "chenghua": 36,
    "tianfu": 38,
    "gaoxin": 12,
    "jinniu": 18,
}
MIN_SCOPES = {
    "wuhou": 40,
    "jinjiang": 15,
    "qingyang": 15,
    "chenghua": 15,
    "tianfu": 20,
    "gaoxin": 8,
    "jinniu": 15,
}
MAX_PENDING = 5  # 公办小学 pending 上限（武侯已 0）


def _load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def filesystem_checks(code: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    schools_doc = _load_yaml(ROOT / "configs" / "districts" / code / "schools.yaml")
    schools = schools_doc.get("schools") or []
    inv = len(schools)
    min_inv = MIN_INVENTORY.get(code, 10)
    if inv < min_inv:
        issues.append(f"inventory {inv} < {min_inv}")

    reg_guide = (schools_doc.get("sources") or {}).get("registration_guide")
    if not reg_guide:
        issues.append("missing registration_guide")

    reg_pts = sum(
        1
        for s in schools
        if s.get("role") == "registration_point"
        and s.get("type") == "public"
        and s.get("level") in ("primary", "nine_year")
    )
    if reg_pts < max(3, min_inv // 4):
        issues.append(f"registration_points {reg_pts} low")

    scraped_path = ROOT / "configs" / "districts" / code / "mapping_scraped.json"
    scopes = 0
    if scraped_path.is_file():
        scraped = json.loads(scraped_path.read_text(encoding="utf-8"))
        scopes = len(scraped.get("school_scopes") or [])
        errors = scraped.get("errors") or []
        if errors and scopes < MIN_SCOPES.get(code, 1):
            issues.append(f"scrape_errors={len(errors)} scopes={scopes}")

    min_scopes = MIN_SCOPES.get(code, 1)
    if min_scopes > 0 and scopes < min_scopes:
        issues.append(f"scopes {scopes} < {min_scopes}")

    if scopes > 0:
        cov = dry_run_coverage(code)
        if cov["unmatched_scope_names"] > 0:
            issues.append(f"unmatched={cov['unmatched_scope_names']}")
        pending = len(cov.get("pending_public_primary") or [])
        limit = 0 if code == "wuhou" else MAX_PENDING
        if pending > limit:
            issues.append(f"pending_public_primary={pending} > {limit}")

    manifest = ROOT / "configs" / "districts" / code / "mirror_intel_manifest.json"
    if manifest.is_file():
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        effective = max(
            int(doc.get("synced") or 0) + int(doc.get("skipped") or 0),
            int(doc.get("processed") or 0),
            len(doc.get("entries") or []),
        )
        if code == "wuhou" and effective < 40:
            issues.append(f"mirror_intel {effective} < 40")
    elif code == "wuhou":
        issues.append("missing mirror_intel_manifest")

    if code == "wuhou":
        mirror_urls = sum(
            1
            for s in schools
            if any(
                "wangdian" in str(u)
                for u in (
                    [(s.get("source_urls") or {}).get("verification_url")]
                    + list((s.get("source_urls") or {}).get("mirror_urls") or [])
                )
                if u
            )
        )
        if mirror_urls < 40:
            issues.append(f"mirror_urls_in_inventory={mirror_urls} < 40")

    return len(issues) == 0, issues


async def db_checks_all(codes: tuple[str, ...]) -> dict[str, dict]:
    from chengdu_edu_storage.db import SessionLocal

    out: dict[str, dict] = {}
    async with SessionLocal() as session:
        for code in codes:
            schools = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM schools s
                        JOIN districts d ON d.id = s.district_id
                        WHERE d.code = :code
                        """
                    ),
                    {"code": code},
                )
            ).scalar_one()
            mapping = (
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
                          AND ep.year = 2025
                          AND ep.school_id IS NOT NULL
                        """
                    ),
                    {"code": code},
                )
            ).mappings().first()
            enrollment = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM enrollment_policies ep
                        JOIN districts d ON d.id = ep.district_id
                        WHERE d.code = :code
                          AND ep.policy_type = 'school_enrollment'
                          AND ep.school_id IS NOT NULL
                        """
                    ),
                    {"code": code},
                )
            ).scalar_one()
            intel_map = (
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
            intel_mirror = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM intel_entries ie
                        JOIN districts d ON d.id = ie.district_id
                        WHERE d.code = :code AND ie.intel_type = 'mirror_page'
                        """
                    ),
                    {"code": code},
                )
            ).scalar_one()
            gov = (
                await session.execute(
                    text(
                        """
                        SELECT COUNT(*) FROM enrollment_policies ep
                        JOIN districts d ON d.id = ep.district_id
                        WHERE d.code = :code
                          AND ep.policy_type = 'gov_policy'
                          AND ep.school_id IS NULL
                        """
                    ),
                    {"code": code},
                )
            ).scalar_one()
            out[code] = {
                "schools": int(schools or 0),
                "mapping_total": int(mapping["total"] or 0),
                "mapping_mapped": int(mapping["mapped"] or 0),
                "enrollment": int(enrollment or 0),
                "intel_mapping": int(intel_map or 0),
                "intel_mirror": int(intel_mirror or 0),
                "gov_policy": int(gov or 0),
            }
    return out


def db_check(code: str, db: dict) -> tuple[bool, list[str]]:
    issues: list[str] = []
    min_inv = MIN_INVENTORY.get(code, 10)
    if db["schools"] < min_inv // 2:
        issues.append(f"db_schools {db['schools']} < {min_inv // 2}")
    if MIN_SCOPES.get(code, 0) > 0 and db["mapping_mapped"] < MIN_SCOPES[code] // 2:
        issues.append(f"db_mapping_mapped {db['mapping_mapped']} low")
    if db["enrollment"] < max(3, min_inv // 4):
        issues.append(f"db_enrollment {db['enrollment']} low")
    if db["intel_mapping"] < 1 and MIN_SCOPES.get(code, 0) > 0:
        issues.append("intel_mapping=0")
    if db["gov_policy"] < 1:
        issues.append("gov_policy=0")
    return len(issues) == 0, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify all districts at Wuhou parity level")
    parser.add_argument("--db", action="store_true")
    args = parser.parse_args()

    failed: list[str] = []
    print("=== verify_district_parity ===")

    fs_results: dict[str, tuple[bool, list[str]]] = {}
    for code in CORE:
        ok, issues = filesystem_checks(code)
        fs_results[code] = (ok, issues)
        if not ok:
            failed.append(code)

    db_data: dict[str, dict] = {}
    if args.db:
        try:
            db_data = asyncio.run(db_checks_all(CORE))
        except Exception as exc:
            print(f"DB unavailable: {exc}")
            return 1

    for code in CORE:
        ok, issues = fs_results[code]
        msg = "PASS" if ok else "FAIL: " + "; ".join(issues)
        if args.db and code in db_data:
            db_ok, db_issues = db_check(code, db_data[code])
            msg += f" | db={db_data[code]}"
            if not db_ok:
                ok = False
                msg += " DB_FAIL: " + "; ".join(db_issues)
                if code not in failed:
                    failed.append(code)
        print(f"{code}: {msg}")

    if failed:
        print("PARITY FAILED:", ", ".join(failed))
        return 1
    print("ALL DISTRICTS PARITY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
