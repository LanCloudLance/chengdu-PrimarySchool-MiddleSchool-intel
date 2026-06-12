"""7 区核心学校 bootstrap：extract → import → school enrollment → promotion。"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# configs/schools.yaml 中已有 seed 的 6 区（武侯走独立 inventory）
MASTER_DISTRICTS = ("jinjiang", "qingyang", "chenghua", "jinniu", "gaoxin", "tianfu")
ALL_CORE = ("wuhou", *MASTER_DISTRICTS)


def run(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    py = sys.executable

    for code in MASTER_DISTRICTS:
        run([py, "scripts/extract_district_schools.py", "--district", code])

    run([py, "scripts/import_schools.py"])

    for code in ALL_CORE:
        run([py, "scripts/import_school_enrollment_policies.py", "--district", code])

    run([py, "scripts/import_district_promotion_policies.py", "--all-core"])

    run([py, "scripts/sync_intel_library.py", "--all-core"])
    run([py, "scripts/import_district_mapping_policies.py", "--all-core"])
    run([py, "scripts/import_school_promotion_targets.py", "--all-core"])

    print("\nbootstrap complete for 7 core districts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
