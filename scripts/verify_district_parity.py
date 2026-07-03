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
# 2026 阈值（OCR 数据不完整，部分区数据来源有限）
MIN_INVENTORY_2026 = {
    "wuhou": 30,
    "jinjiang": 25,
    "qingyang": 32,
    "chenghua": 36,
    "tianfu": 15,
    "gaoxin": 12,
    "jinniu": 18,
}
MIN_SCOPES_2026 = {
    "wuhou": 20,
    "jinjiang": 15,
    "qingyang": 15,
    "chenghua": 15,
    "tianfu": 10,
    "gaoxin": 8,
    "jinniu": 15,
}
MAX_PENDING = 5  # 公办小学 pending 上限（武侯已 0）
KNOWN_MAPPING_STATUSES = (
    "verified",
    "reference",
    "pending_review",
    "pending_official",
)


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


def _load_file_counts(code: str, year: int = 2025) -> dict:
    """从文件系统加载学校数和有效划片数。"""
    schools_doc = _load_yaml(ROOT / "configs" / "districts" / code / "schools.yaml")
    file_schools = len(schools_doc.get("schools") or [])

    if year >= 2026:
        scraped_path = ROOT / "configs" / "districts" / code / "mapping_scraped_2026.json"
    else:
        scraped_path = ROOT / "configs" / "districts" / code / "mapping_scraped.json"
    file_scopes = 0
    if scraped_path.is_file():
        scraped = json.loads(scraped_path.read_text(encoding="utf-8"))
        scopes = scraped.get("school_scopes") or []
        # 统计有效划片（长度>=8且包含关键词）
        import re
        kw = re.compile(r"[至界路街道巷大道区社区苑村]")
        file_scopes = sum(1 for s in scopes if len(s.get("enrollment_scope", "")) >= 8 and kw.search(s.get("enrollment_scope", "")))

    return {"file_schools": file_schools, "file_scopes": file_scopes}


async def db_checks_all(
    codes: tuple[str, ...], year: int = 2025
) -> dict[str, dict]:
    from chengdu_edu_storage.db import SessionLocal

    out: dict[str, dict] = {}
    async with SessionLocal() as session:
        for code in codes:
            # 加载文件系统计数
            file_counts = _load_file_counts(code, year=year)
            
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
                               ) AS mapped,
                               COUNT(*) FILTER (
                                 WHERE ep.fields->>'mapping_status' = 'verified'
                               ) AS verified,
                               COUNT(*) FILTER (
                                 WHERE ep.fields->>'mapping_status' = 'reference'
                               ) AS reference,
                               COUNT(*) FILTER (
                                 WHERE ep.fields->>'mapping_status' = 'pending_review'
                               ) AS pending_review,
                               COUNT(*) FILTER (
                                 WHERE ep.fields->>'mapping_status' = 'pending_official'
                               ) AS pending_official,
                               COUNT(*) FILTER (
                                 WHERE COALESCE(ep.fields->>'mapping_status', '') NOT IN (
                                   'verified',
                                   'reference',
                                   'pending_review',
                                   'pending_official'
                                 )
                               ) AS unknown_status
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
                "verified": int(mapping["verified"] or 0),
                "reference": int(mapping["reference"] or 0),
                "pending_review": int(mapping["pending_review"] or 0),
                "pending_official": int(mapping["pending_official"] or 0),
                "unknown_status": int(mapping["unknown_status"] or 0),
                "enrollment": int(enrollment or 0),
                "intel_mapping": int(intel_map or 0),
                "intel_mirror": int(intel_mirror or 0),
                "gov_policy": int(gov or 0),
                **file_counts,
            }
    return out


def db_check(
    code: str,
    db: dict,
    min_inv: dict[str, int] | None = None,
    min_scopes: dict[str, int] | None = None,
    year: int = 2025,
) -> tuple[bool, list[str]]:
    issues: list[str] = []
    if min_inv is None:
        min_inv = MIN_INVENTORY
    if min_scopes is None:
        min_scopes = MIN_SCOPES
    file_schools = db.get("file_schools", 0)
    file_scopes = db.get("file_scopes", 0)

    # 检查1：DB学校数应与文件一致（允许±2的误差）
    if file_schools > 0:
        school_diff = abs(db["schools"] - file_schools)
        if school_diff > 2:
            issues.append(f"db_schools={db['schools']} vs file_schools={file_schools} (diff={school_diff})")

    if year >= 2026:
        return _db_check_2026(code, db, min_scopes=min_scopes)

    # 检查2：DB划片数应接近文件划片数（mapped应至少达到文件的80%）
    if file_scopes > 0:
        min_mapped = int(file_scopes * 0.8)
        if db["mapping_mapped"] < min_mapped:
            issues.append(f"db_mapping_mapped={db['mapping_mapped']} < 80% of file_scopes={file_scopes} (need {min_mapped})")

    # 检查3：mapping_total应至少达到MIN_SCOPES
    if min_scopes.get(code, 0) > 0 and db["mapping_total"] < min_scopes[code]:
        issues.append(f"db_mapping_total {db['mapping_total']} < {min_scopes[code]}")
    
    # 检查4：enrollment数应接近学校数（至少达到80%）
    if db["schools"] > 0:
        min_enrollment = int(db["schools"] * 0.8)
        if db["enrollment"] < min_enrollment:
            issues.append(f"db_enrollment={db['enrollment']} < 80% of db_schools={db['schools']} (need {min_enrollment})")
    
    # 检查5：intel_mapping应至少有1条
    if db["intel_mapping"] < 1 and MIN_SCOPES.get(code, 0) > 0:
        issues.append("intel_mapping=0")
    
    # 检查6：gov_policy应至少有1条
    if db["gov_policy"] < 1:
        issues.append("gov_policy=0")
    
    # 检查7：mapping_mapped应该接近mapping_total（允许pending_official占10%）
    if db["mapping_total"] > 0:
        mapped_ratio = db["mapping_mapped"] / db["mapping_total"]
        if mapped_ratio < 0.9:
            issues.append(f"db_mapping_mapped={db['mapping_mapped']}/{db['mapping_total']} ({mapped_ratio:.1%} < 90%)")
    
    return len(issues) == 0, issues


def _db_check_2026(
    code: str,
    db: dict,
    *,
    min_scopes: dict[str, int],
) -> tuple[bool, list[str]]:
    """2026 数据分层校验。

    2026 年数据包含 OCR 待复核和天府学区制改革占位，不能沿用
    2025 年 mapped/total >= 90% 的单一口径。
    """
    issues: list[str] = []
    file_schools = db.get("file_schools", 0)
    if file_schools > 0:
        school_diff = abs(db["schools"] - file_schools)
        if school_diff > 2:
            issues.append(
                f"db_schools={db['schools']} vs file_schools={file_schools} "
                f"(diff={school_diff})"
            )

    if min_scopes.get(code, 0) > 0 and db["mapping_total"] < min_scopes[code]:
        issues.append(f"db_mapping_total {db['mapping_total']} < {min_scopes[code]}")

    if db["schools"] > 0:
        min_enrollment = int(db["schools"] * 0.8)
        if db["enrollment"] < min_enrollment:
            issues.append(
                f"db_enrollment={db['enrollment']} < 80% of "
                f"db_schools={db['schools']} (need {min_enrollment})"
            )

    if db["intel_mapping"] < 1 and MIN_SCOPES.get(code, 0) > 0:
        issues.append("intel_mapping=0")
    if db["gov_policy"] < 1:
        issues.append("gov_policy=0")

    status_total = sum(int(db.get(status, 0)) for status in KNOWN_MAPPING_STATUSES)
    status_total += int(db.get("unknown_status", 0))
    if status_total != db["mapping_total"]:
        issues.append(
            f"mapping_status_total={status_total} != mapping_total={db['mapping_total']}"
        )
    if db.get("unknown_status", 0):
        issues.append(f"unknown_mapping_status={db['unknown_status']}")

    if db["mapping_total"] <= 0:
        issues.append("db_mapping_total=0")
        return False, issues

    actionable = (
        int(db.get("verified", 0))
        + int(db.get("reference", 0))
        + int(db.get("pending_review", 0))
    )
    pending = int(db.get("pending_official", 0))
    if code == "tianfu":
        if pending != db["mapping_total"]:
            issues.append(
                "tianfu_2026_expected_all_pending_official_until_reform_mapping"
            )
    else:
        if actionable <= 0:
            issues.append("no_verified_reference_or_pending_review_rows")
        pending_ratio = pending / db["mapping_total"]
        if pending_ratio > 0.4:
            issues.append(
                f"pending_official={pending}/{db['mapping_total']} "
                f"({pending_ratio:.1%} > 40%)"
            )

    return len(issues) == 0, issues


def format_db_status(d: dict, *, year: int) -> str:
    file_vs_db = (
        f"schools(file={d.get('file_schools', '?')}/db={d['schools']}) "
        f"scopes(file={d.get('file_scopes', '?')}/mapped={d['mapping_mapped']}/"
        f"{d['mapping_total']}) "
        f"enroll={d['enrollment']}"
    )
    meta = (
        f"intel_map={d['intel_mapping']} intel_mirror={d['intel_mirror']} "
        f"gov={d['gov_policy']}"
    )
    if year >= 2026:
        status = (
            f"status(v={d.get('verified', 0)} ref={d.get('reference', 0)} "
            f"review={d.get('pending_review', 0)} "
            f"pending={d.get('pending_official', 0)} "
            f"unknown={d.get('unknown_status', 0)})"
        )
        return f"{file_vs_db} {status} {meta}"
    return f"{file_vs_db} {meta}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify all districts at Wuhou parity level")
    parser.add_argument("--db", action="store_true")
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="数据年份；2026 时使用降级阈值（OCR 数据不完整）",
    )
    args = parser.parse_args()

    year = args.year
    if year >= 2026:
        min_inv_map = MIN_INVENTORY_2026
        min_scopes_map = MIN_SCOPES_2026
    else:
        min_inv_map = MIN_INVENTORY
        min_scopes_map = MIN_SCOPES

    failed: list[str] = []
    print(f"=== verify_district_parity (year={year}) ===")

    fs_results: dict[str, tuple[bool, list[str]]] = {}
    for code in CORE:
        ok, issues = filesystem_checks(code)
        fs_results[code] = (ok, issues)
        if not ok:
            failed.append(code)

    db_data: dict[str, dict] = {}
    if args.db:
        try:
            db_data = asyncio.run(db_checks_all(CORE, year=year))
        except Exception as exc:
            print(f"DB unavailable: {exc}")
            return 1

    for code in CORE:
        ok, issues = fs_results[code]
        if args.db and code in db_data:
            # 传入选用的阈值用于 DB 检查
            db_ok, db_issues = db_check(
                code,
                db_data[code],
                min_inv=min_inv_map,
                min_scopes=min_scopes_map,
                year=year,
            )
            d = db_data[code]
            status_line = format_db_status(d, year=year)
            if not db_ok:
                ok = False
                msg = f"FAIL: {'; '.join(issues + db_issues)} | {status_line}"
                if code not in failed:
                    failed.append(code)
            elif not ok:
                msg = f"FAIL(fs): {'; '.join(issues)} | {status_line}"
            else:
                msg = f"PASS | {status_line}"
        else:
            msg = "PASS" if ok else "FAIL: " + "; ".join(issues)
        print(f"{code}: {msg}")

    if failed:
        print("PARITY FAILED:", ", ".join(failed))
        return 1
    print("ALL DISTRICTS PARITY PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
