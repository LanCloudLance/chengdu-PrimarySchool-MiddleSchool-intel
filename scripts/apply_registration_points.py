"""根据 4 月 edu 登记点公告 URL，将 inventory 中公办小学标记为 registration_point。"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "configs" / "sources.yaml"
DISTRICT_YAML_TMPL = "configs/districts/{code}/schools.yaml"

PRIMARY_LEVELS = {"primary", "nine_year"}


def registration_url_for(district_code: str) -> str | None:
    doc = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    for entry in doc.get("sources") or []:
        if entry.get("district_code") == district_code and entry.get("registration_url"):
            return entry["registration_url"]
    return None


def apply_district(district_code: str, *, dry_run: bool = False) -> dict:
    path = ROOT / DISTRICT_YAML_TMPL.format(code=district_code)
    if not path.is_file():
        return {"updated": 0, "reason": "no_schools_yaml"}

    reg_url = registration_url_for(district_code)
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schools = doc.get("schools") or []
    updated = 0
    candidates = 0
    confirmed = 0

    sources = dict(doc.get("sources") or {})
    if reg_url:
        sources["registration_guide"] = reg_url
        doc["sources"] = sources

    for school in schools:
        role = school.get("role")
        if role == "registration_point_candidate":
            candidates += 1
        if role == "registration_point":
            confirmed += 1

        is_public_primary = (
            school.get("type") == "public" and school.get("level") in PRIMARY_LEVELS
        )
        if not is_public_primary:
            continue

        changed = False
        if role != "registration_point":
            school["role"] = "registration_point"
            changed = True
        if reg_url and school.get("verification_source") != reg_url:
            school["verification_source"] = reg_url
            changed = True
        if changed:
            updated += 1

    doc["schools"] = schools
    if not dry_run:
        path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    return {
        "district": district_code,
        "updated": updated,
        "registration_guide": reg_url,
        "public_primary_registration_points": sum(
            1
            for s in schools
            if s.get("type") == "public"
            and s.get("level") in PRIMARY_LEVELS
            and s.get("role") == "registration_point"
        ),
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply registration_point roles from edu guide URLs")
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    targets = args.districts or (
        ["jinjiang", "qingyang", "wuhou", "chenghua", "jinniu", "gaoxin", "tianfu"]
        if args.all_core
        else ["wuhou"]
    )

    for code in targets:
        result = apply_district(code, dry_run=args.dry_run)
        print(
            f"{code}: updated={result.get('updated', 0)} "
            f"registration_points={result.get('public_primary_registration_points', 0)} "
            f"guide={result.get('registration_guide')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
