"""区县 inventory 一键对齐：sync → build → verify → import → prune。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CORE_DISTRICTS = (
    "jinjiang",
    "qingyang",
    "wuhou",
    "chenghua",
    "jinniu",
    "gaoxin",
    "tianfu",
)

WUHOU_PIPELINE = [
    [sys.executable, "scripts/sync_wuhou_alternate_urls.py"],
    [sys.executable, "scripts/build_wuhou_inventory.py"],
    [sys.executable, "scripts/verify_wuhou_schools.py", "--pending-only"],
    [sys.executable, "scripts/generate_wuhou_checklist.py"],
]


def run_step(cmd: list[str]) -> None:
    print(f"\n>>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Align district school inventory")
    parser.add_argument(
        "--district",
        default="wuhou",
        choices=CORE_DISTRICTS,
        help="district code",
    )
    parser.add_argument("--skip-verify", action="store_true")
    args = parser.parse_args()

    if args.district == "wuhou":
        steps = list(WUHOU_PIPELINE)
        if args.skip_verify:
            steps = [s for s in steps if "verify_wuhou" not in s[1]]
        for step in steps:
            run_step(step)
    else:
        run_step(
            [sys.executable, "scripts/extract_district_schools.py", "--district", args.district]
        )

    run_step([sys.executable, "scripts/import_schools.py"])
    run_step(
        [
            sys.executable,
            "scripts/import_school_enrollment_policies.py",
            "--district",
            args.district,
        ]
    )
    run_step(
        [
            sys.executable,
            "scripts/import_district_promotion_policies.py",
            "--district",
            args.district,
        ]
    )
    run_step([sys.executable, "scripts/sync_intel_library.py", "--district", args.district])
    run_step(
        [
            sys.executable,
            "scripts/import_district_mapping_policies.py",
            "--district",
            args.district,
        ]
    )
    run_step(
        [
            sys.executable,
            "scripts/import_school_promotion_targets.py",
            "--district",
            args.district,
        ]
    )
    print(f"\naligned district: {args.district}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
