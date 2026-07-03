"""七区深度管线：对齐武侯 W1–W4 能力（划片/intel/登记点/入库/镜像）。"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CORE = ("jinjiang", "qingyang", "wuhou", "chenghua", "jinniu", "gaoxin", "tianfu")
OCR_DISTRICTS = ("jinniu", "gaoxin", "wuhou")
PY = sys.executable


def run(cmd: list[str], *, pause: float = 0.0, check: bool = True) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=check)
    if pause:
        time.sleep(pause)


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep bootstrap all 7 districts to Wuhou parity")
    parser.add_argument("--district", action="append", dest="districts", help="仅处理指定区（可重复）")
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-db", action="store_true", help="跳过需 Docker 的 import/sync")
    parser.add_argument("--skip-ocr", action="store_true")
    args = parser.parse_args()
    targets = tuple(args.districts) if args.districts else CORE

    run([PY, "scripts/seed_inventory_from_global.py", "--all-core"])

    if not args.skip_scrape:
        for code in targets:
            ocr_args = ["--ocr"] if code in OCR_DISTRICTS and not args.skip_ocr else []
            run(
                [PY, "scripts/scrape_district_mapping.py", "--district", code, *ocr_args],
                pause=2.0,
            )
            run([PY, "scripts/expand_inventory_from_mapping.py", "--district", code])
            promo_cfg = ROOT / "configs" / "district_mapping_sources.yaml"
            if promo_cfg.is_file():
                cfg = yaml.safe_load(promo_cfg.read_text(encoding="utf-8"))
                promos = (cfg.get("districts") or {}).get(code, {}).get("promotion_urls") or []
                if promos and not args.skip_ocr:
                    run(
                        [PY, "scripts/scrape_district_mapping.py", "--district", code, "--promotion-only", "--ocr"],
                        pause=1.5,
                    )

    run([PY, "scripts/apply_registration_points.py", "--all-core"])

    if args.skip_db:
        print("\nbootstrap_district_parity: filesystem phase done (--skip-db)")
        return 0

    run([PY, "scripts/import_schools.py"])
    for code in targets:
        run([PY, "scripts/import_school_enrollment_policies.py", "--district", code])
    for code in targets:
        run([PY, "scripts/import_district_mapping_policies.py", "--district", code])
    cfg = yaml.safe_load((ROOT / "configs/district_mapping_sources.yaml").read_text(encoding="utf-8"))
    for code in targets:
        promos = (cfg.get("districts") or {}).get(code, {}).get("promotion_urls") or []
        if promos:
            run([PY, "scripts/import_school_promotion_targets.py", "--district", code])

    ocr_intel = [] if args.skip_ocr else ["--ocr"]
    for code in targets:
        run([PY, "scripts/sync_intel_library.py", "--district", code, *ocr_intel])
    for code in targets:
        run(
            [PY, "scripts/sync_mirror_intel.py", "--district", code, "--from-inventory", "--workers", "1"],
            check=False,
        )

    print("\nbootstrap_district_parity: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
