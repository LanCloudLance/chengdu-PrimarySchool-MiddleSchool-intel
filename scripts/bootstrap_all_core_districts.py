"""七区批量首遍管线：scrape → expand inventory → registration → import DB。"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORE = ("jinjiang", "qingyang", "wuhou", "chenghua", "jinniu", "gaoxin", "tianfu")
SCRAPE_DISTRICTS = ("jinjiang", "qingyang", "chenghua", "gaoxin", "tianfu")
PY = sys.executable


def run(cmd: list[str], *, pause: float = 0.0) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)
    if pause:
        time.sleep(pause)


def main() -> int:
    for code in SCRAPE_DISTRICTS:
        run([PY, "scripts/scrape_district_mapping.py", "--district", code], pause=2.5)
        run([PY, "scripts/expand_inventory_from_mapping.py", "--district", code])
    print("\n>>> skip scrape: jinniu (bendibao 正文缺失), wuhou (样板已验收)")

    run([PY, "scripts/apply_registration_points.py", "--all-core"])
    run([PY, "scripts/import_schools.py"])
    run([PY, "scripts/import_school_enrollment_policies.py", "--district", "wuhou"])
    for code in CORE:
        if code == "wuhou":
            continue
        run([PY, "scripts/import_school_enrollment_policies.py", "--district", code])
    run([PY, "scripts/import_district_mapping_policies.py", "--all-core"])
    run([PY, "scripts/import_school_promotion_targets.py", "--district", "wuhou"])
    run([PY, "scripts/sync_mirror_intel.py", "--district", "wuhou", "--from-inventory"])
    print("\nbootstrap_all_core_districts: done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
