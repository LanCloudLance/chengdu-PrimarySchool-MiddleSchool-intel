"""从 configs/schools.yaml 提取单区学校到 configs/districts/{code}/schools.yaml。"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MASTER = ROOT / "configs" / "schools.yaml"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--district", required=True)
    args = parser.parse_args()
    code = args.district

    master = yaml.safe_load(MASTER.read_text(encoding="utf-8"))
    schools = [s for s in master["schools"] if s.get("district_code") == code]
    if not schools:
        print(f"no schools for district {code}", file=sys.stderr)
        return 1

    out_dir = ROOT / "configs" / "districts" / code
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "schools.yaml"
    doc = {
        "district_code": code,
        "data_year": master.get("data_year", 2026),
        "notes": f"从 configs/schools.yaml 提取的 {code} 区学校（{len(schools)} 校）",
        "inventory_summary": {
            "total": len(schools),
            "listed": len(schools),
            "enriched": 0,
            "verified": sum(1 for s in schools if s.get("verified")),
        },
        "schools": schools,
    }
    out_path.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {out_path} ({len(schools)} schools)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
