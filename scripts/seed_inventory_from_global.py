"""将 configs/schools.yaml 中各区 seed 校合并进分区 schools.yaml（不覆盖已有条目）。"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
GLOBAL = ROOT / "configs" / "schools.yaml"
CORE = ("jinjiang", "qingyang", "wuhou", "chenghua", "jinniu", "gaoxin", "tianfu")


def merge_district(code: str, *, dry_run: bool = False) -> dict:
    if not GLOBAL.is_file():
        return {"added": 0, "reason": "no_global_schools"}

    global_doc = yaml.safe_load(GLOBAL.read_text(encoding="utf-8")) or {}
    seeds = [s for s in global_doc.get("schools") or [] if s.get("district_code") == code]

    path = ROOT / "configs" / "districts" / code / "schools.yaml"
    if path.is_file():
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        doc = {
            "district_code": code,
            "data_year": global_doc.get("data_year", 2026),
            "notes": f"从 global schools.yaml 种子合并（{code}）",
            "schools": [],
        }

    schools = list(doc.get("schools") or [])
    existing = {s["name"] for s in schools if s.get("name")}
    added = 0
    for seed in seeds:
        name = seed.get("name")
        if not name or name in existing:
            continue
        row = dict(seed)
        row["district_code"] = code
        schools.append(row)
        existing.add(name)
        added += 1

    schools.sort(key=lambda s: s.get("name") or "")
    doc["schools"] = schools
    doc["inventory_summary"] = {
        "total": len(schools),
        "listed": sum(1 for s in schools if not s.get("verified")),
        "enriched": sum(1 for s in schools if s.get("source_urls")),
        "verified": sum(1 for s in schools if s.get("verified")),
    }

    if not dry_run and added:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")

    return {"added": added, "total": len(schools), "seeds": len(seeds)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge global school seeds into district inventory")
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    targets = CORE if args.all_core else (args.districts or list(CORE))

    for code in targets:
        result = merge_district(code, dry_run=args.dry_run)
        print(f"{code}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
