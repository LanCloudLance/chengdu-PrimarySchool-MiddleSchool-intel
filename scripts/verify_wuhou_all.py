"""武侯样板区统一验收：W1 划片 + W2 对口 + pytest（任务完成必跑）。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "bin" / "python"


def _run(label: str, args: list[str]) -> int:
    print(f"\n{'=' * 60}\n{label}\n{'=' * 60}")
    result = subprocess.run(args, cwd=ROOT)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all Wuhou acceptance checks")
    parser.add_argument("--db", action="store_true", help="Also run DB checks (needs Docker)")
    parser.add_argument("--skip-pytest", action="store_true")
    args = parser.parse_args()

    py = str(PY if PY.is_file() else sys.executable)
    failed: list[str] = []

    steps = [
        ("W1.4 划片验收", [py, "scripts/verify_wuhou_mapping.py"] + (["--db"] if args.db else [])),
        ("W2.4 对口验收", [py, "scripts/verify_wuhou_promotion.py"] + (["--db"] if args.db else [])),
        ("W3.4 门户验收", [py, "scripts/verify_wuhou_portal.py"]),
        ("W4.4 运营化验收", [py, "scripts/verify_wuhou_w4.py"] + (["--db"] if args.db else [])),
    ]
    steps.append(("七区批量验收", [py, "scripts/verify_all_districts.py"] + (["--db"] if args.db else [])))
    steps.append(
        ("七区武侯同级验收", [py, "scripts/verify_district_parity.py"] + (["--db"] if args.db else []))
    )
    if not args.skip_pytest:
        steps.append(("pytest", [py, "-m", "pytest", "-q"]))

    for label, cmd in steps:
        if _run(label, cmd) != 0:
            failed.append(label)

    print(f"\n{'=' * 60}")
    if failed:
        print("FAILED:", ", ".join(failed))
        return 1
    print("ALL PASS: W1 + W2 + W3 + W4 + 7区" + ("" if args.skip_pytest else " + pytest"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
