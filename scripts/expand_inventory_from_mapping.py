"""从 mapping_scraped.json 补全区县 schools.yaml inventory（复制新区第一遍用）。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def expand_district(district_code: str, *, dry_run: bool = False) -> dict:
    scraped_path = ROOT / "configs" / "districts" / district_code / "mapping_scraped.json"
    schools_path = ROOT / "configs" / "districts" / district_code / "schools.yaml"
    if not scraped_path.is_file():
        return {"added": 0, "reason": "no_mapping_scraped"}

    scraped = json.loads(scraped_path.read_text(encoding="utf-8"))
    scope_names = {
        row["school_name"]
        for row in scraped.get("school_scopes") or []
        if row.get("school_name")
    }
    if not scope_names:
        return {"added": 0, "reason": "no_scopes"}

    if schools_path.is_file():
        doc = yaml.safe_load(schools_path.read_text(encoding="utf-8")) or {}
    else:
        doc = {
            "district_code": district_code,
            "data_year": scraped.get("data_year", 2025),
            "notes": f"从 mapping_scraped 自动补全 inventory（{district_code}）",
            "schools": [],
        }

    schools = list(doc.get("schools") or [])
    existing = {s["name"] for s in schools}
    source_url = None
    for article in scraped.get("articles") or []:
        if article.get("scopes", 0) > 0:
            source_url = article.get("url")
            break

    added = 0
    for name in sorted(scope_names):
        if name in existing:
            continue
        schools.append(
            {
                "name": name,
                "short_name": name.replace("成都市", "")[:12] or None,
                "district_code": district_code,
                "type": "public",
                "level": "primary",
                "data_year": doc.get("data_year", scraped.get("data_year", 2025)),
                "verified": False,
                "verification_source": source_url,
                "role": "registration_point",
            }
        )
        existing.add(name)
        added += 1

    schools.sort(key=lambda s: s["name"])
    doc["schools"] = schools
    doc["inventory_summary"] = {
        "total": len(schools),
        "listed": sum(1 for s in schools if not s.get("verified")),
        "enriched": 0,
        "verified": sum(1 for s in schools if s.get("verified")),
    }

    if not dry_run:
        schools_path.parent.mkdir(parents=True, exist_ok=True)
        schools_path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    return {
        "district": district_code,
        "added": added,
        "total": len(schools),
        "scope_names": len(scope_names),
        "dry_run": dry_run,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Expand district inventory from mapping scrape")
    parser.add_argument("--district", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = expand_district(args.district, dry_run=args.dry_run)
    print(
        f"{args.district}: added={result.get('added', 0)} "
        f"total={result.get('total', 0)} scopes={result.get('scope_names', 0)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
