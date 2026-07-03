"""校验武侯区学校官网并回写 schools.yaml 的 verified 状态。"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import httpx
import yaml

from wuhou_url_utils import (
    HTTP_TIMEOUT,
    HEADERS,
    collect_alternate_urls,
    verify_mirror_only,
    verify_school_website,
)

ROOT = Path(__file__).resolve().parent.parent
WUHOU_YAML = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
ENRICHMENT_YAML = ROOT / "configs" / "districts" / "wuhou" / "enrichment.yaml"
REPORT_PATH = ROOT / "configs" / "districts" / "wuhou" / "verification_report.json"


def load_enrichment() -> dict:
    return yaml.safe_load(ENRICHMENT_YAML.read_text(encoding="utf-8")) or {}


async def verify_wuhou_schools(*, write_back: bool = True, pending_only: bool = False) -> dict:
    enrichment = load_enrichment()
    no_website = set((enrichment.get("no_website") or {}).keys())
    doc = yaml.safe_load(WUHOU_YAML.read_text(encoding="utf-8"))
    schools = doc["schools"]

    url_results: dict[str, dict] = {}
    school_results: dict[str, dict] = {}

    async def check_school(
        client: httpx.AsyncClient,
        index: int,
        school: dict,
        *,
        tag: str,
    ) -> bool:
        urls = school.get("source_urls") or {}
        primary = urls.get("website")
        mirror_only = not primary and school["name"] in no_website
        if not primary and not mirror_only:
            return True
        if pending_only and school.get("inventory_status") == "verified":
            return True
        if index > 0:
            await asyncio.sleep(1.2 if tag == "retry" else 0.4)
        if mirror_only:
            result = await verify_mirror_only(
                client,
                school_name=school["name"],
                enrichment=enrichment,
            )
        else:
            result = await verify_school_website(
                client,
                primary=primary,
                school_name=school["name"],
                enrichment=enrichment,
            )
        school_results[school["name"]] = result
        checked_url = result.get("url") or primary
        if checked_url:
            url_results[checked_url] = result
        via = result.get("via", "primary")
        ok = result.get("ok")
        mode = "mirror" if mirror_only else "site"
        print(
            f"  [{index + 1}/{len(schools)}] {school['name'][:16]} "
            f"-> ok={ok} via={via} ({mode}/{tag})"
        )
        if not ok:
            school["verified"] = False
            if school.get("inventory_status") == "verified":
                school["inventory_status"] = "enriched"
            return False

        school["verified"] = True
        school["verified_at"] = date.today().isoformat()
        school["inventory_status"] = "verified"
        resolved = result.get("url", primary)
        src = dict(urls)
        src["verification_url"] = resolved
        src["verification_via"] = via
        if mirror_only:
            alternates = collect_alternate_urls(
                primary=None,
                school_name=school["name"],
                enrichment=enrichment,
            )
            if alternates:
                src["mirror_urls"] = [a["url"] for a in alternates]
        else:
            alternates = collect_alternate_urls(
                primary=primary,
                school_name=school["name"],
                enrichment=enrichment,
            )
            if alternates:
                src["alternate_urls"] = [a["url"] for a in alternates]
            if resolved != primary:
                src["website_resolved"] = resolved
        school["source_urls"] = src
        return True

    async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=HEADERS) as client:
        failed: list[str] = []
        for index, school in enumerate(schools):
            if not await check_school(client, index, school, tag="check"):
                failed.append(school["name"])

    if failed:
        print(f"  retrying {len(failed)} failed schools once after cooldown...")
        await asyncio.sleep(20)
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, headers=HEADERS) as client:
            for index, school in enumerate(schools):
                if school["name"] not in failed:
                    continue
                await check_school(client, index, school, tag="retry")

    summary = {
        "verified_at": date.today().isoformat(),
        "schools_total": len(schools),
        "with_website": len(school_results),
        "websites_ok": sum(1 for r in school_results.values() if r.get("ok")),
        "verified_via_primary": sum(
            1 for r in school_results.values() if r.get("ok") and r.get("via") == "primary"
        ),
        "verified_via_alternate": sum(
            1 for r in school_results.values() if r.get("ok") and r.get("via") == "alternate"
        ),
        "verified_via_mirror_only": sum(
            1 for r in school_results.values() if r.get("ok") and r.get("via") == "mirror_only"
        ),
    }
    doc["inventory_summary"] = {
        "total": len(schools),
        "listed": sum(1 for s in schools if s.get("inventory_status") == "listed"),
        "enriched": sum(1 for s in schools if s.get("inventory_status") == "enriched"),
        "verified": sum(1 for s in schools if s.get("inventory_status") == "verified"),
    }
    summary["schools_verified"] = doc["inventory_summary"]["verified"]
    summary["school_checks"] = school_results
    summary["url_checks"] = url_results
    REPORT_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if write_back:
        WUHOU_YAML.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        sync_verified_websites(doc["schools"])
    return summary


def sync_verified_websites(schools: list[dict]) -> None:
    enrichment = load_enrichment()
    verified = sorted(
        {
            (s.get("source_urls") or {}).get("verification_url")
            or (s.get("source_urls") or {}).get("website")
            for s in schools
            if s.get("inventory_status") == "verified"
        }
        - {None}
    )
    enrichment["verified_websites"] = verified
    ENRICHMENT_YAML.write_text(
        yaml.safe_dump(enrichment, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


async def main() -> None:
    pending_only = "--pending-only" in sys.argv
    summary = await verify_wuhou_schools(pending_only=pending_only)
    print(
        f"websites checked: {summary['with_website']}, "
        f"ok: {summary['websites_ok']}, "
        f"primary: {summary['verified_via_primary']}, "
        f"alternate: {summary['verified_via_alternate']}, "
        f"mirror_only: {summary.get('verified_via_mirror_only', 0)}, "
        f"schools verified: {summary['schools_verified']}"
    )
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
