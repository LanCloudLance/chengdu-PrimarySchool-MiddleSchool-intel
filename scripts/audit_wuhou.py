"""武侯区效果验证：inventory 汇总 + 逐校复验已记录的 verification_url。"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
WUHOU_YAML = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
REPORT = ROOT / "configs" / "districts" / "wuhou" / "audit_report.json"

sys.path.insert(0, str(ROOT / "scripts"))
from wuhou_url_utils import HEADERS, HTTP_TIMEOUT, _mirror_name_ok, check_url

OUT = Path(__file__).resolve().parent


async def audit_live(schools: list[dict]) -> list[dict]:
    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=HEADERS) as client:
        for index, school in enumerate(schools):
            urls = school.get("source_urls") or {}
            url = urls.get("verification_url")
            via = urls.get("verification_via", "primary")
            row = {
                "name": school["name"],
                "inventory_status": school.get("inventory_status"),
                "verification_via": via,
                "url": url,
                "live_ok": None,
                "http_status": None,
                "error": None,
            }
            if not url:
                row["live_ok"] = False
                row["error"] = "missing verification_url"
                rows.append(row)
                continue
            if index > 0:
                await asyncio.sleep(0.3)
            mirror_only = via == "mirror_only"
            probe = await check_url(
                client,
                url,
                school_name=school["name"],
                require_name_match=mirror_only or "bendibao.com" in url,
                mirror_only=mirror_only,
            )
            row["live_ok"] = probe.get("ok", False)
            row["http_status"] = probe.get("http_status")
            row["error"] = probe.get("error")
            row["url_used"] = probe.get("url")
            rows.append(row)
            mark = "OK" if row["live_ok"] else "FAIL"
            print(f"  [{index + 1}/{len(schools)}] {mark} {school['name'][:18]} via={via}")
    return rows


def main() -> int:
    doc = yaml.safe_load(WUHOU_YAML.read_text(encoding="utf-8"))
    schools = doc["schools"]
    inventory = doc.get("inventory_summary", {})
    via_counts = Counter(
        (s.get("source_urls") or {}).get("verification_via", "none")
        for s in schools
        if s.get("inventory_status") == "verified"
    )

    print("=== 武侯区 Inventory（YAML）===")
    print(json.dumps(inventory, ensure_ascii=False, indent=2))
    print("\n验证路径分布:", dict(via_counts))
    print(f"\n=== 实时复验 verification_url（{len(schools)} 校）===\n")

    rows = asyncio.run(audit_live(schools))
    ok = sum(1 for r in rows if r.get("live_ok"))
    failed = [r for r in rows if not r.get("live_ok")]

    report = {
        "audited_at": date.today().isoformat(),
        "inventory": inventory,
        "verified_via": dict(via_counts),
        "live_checked": len(rows),
        "live_ok": ok,
        "live_failed": len(failed),
        "failed": failed,
        "samples_ok": [r for r in rows if r.get("live_ok")][:5],
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n=== 结果：{ok}/{len(rows)} 路径实时可达 ===")
    if failed:
        print("失败校：")
        for r in failed:
            print(f"  - {r['name']}: {r.get('error') or r.get('url')}")
    print(f"\nreport: {REPORT}")
    return 0 if not failed and inventory.get("verified") == len(schools) else 1


if __name__ == "__main__":
    raise SystemExit(main())
