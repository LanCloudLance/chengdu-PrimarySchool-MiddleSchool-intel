"""校验 configs 中政策数据源与学校主数据（2026）。"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SOURCES_CONFIG = ROOT / "configs" / "sources.yaml"
SCHOOLS_CONFIG = ROOT / "configs" / "schools.yaml"
DISTRICT_SCHOOLS_GLOB = "configs/districts/*/schools.yaml"
WUHOU_SCHOOLS = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
WUHOU_VERIFY_REPORT = ROOT / "configs" / "districts" / "wuhou" / "verification_report.json"
REPORT_PATH = ROOT / "configs" / "verification_report.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

POLICY_YEAR = 2026
SCOPE_RE = re.compile(
    r"(?:公办小学入学对象|本区户籍适龄儿童|新区户籍适龄儿童|金牛区户籍适龄儿童)"
)
TIME_RE = re.compile(r"5月6日[—\-~至]+12日|5月6日10[：:]00")


def _page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text("\n", strip=True)


async def _fetch(client: httpx.AsyncClient, url: str) -> tuple[int | None, str, str | None]:
    try:
        resp = await client.get(url)
        text = _page_text(resp.text)
        return resp.status_code, text, None
    except httpx.HTTPError as exc:
        return None, "", str(exc)


def _check_policy_page(text: str, expected_year: int) -> dict:
    blocked = "拼图验证" in text
    has_year = str(expected_year) in text
    return {
        "blocked": blocked,
        "has_year": has_year,
        "has_scope": bool(SCOPE_RE.search(text)),
        "has_registration_time": bool(TIME_RE.search(text)),
        "content_length": len(text),
        "ok": not blocked and has_year and len(text) > 500,
    }


async def verify_sources(expected_year: int = POLICY_YEAR) -> list[dict]:
    from policy_url_utils import NEWS_CANDIDATE_POOL, bendibao_variants, probe_url

    data = yaml.safe_load(SOURCES_CONFIG.read_text(encoding="utf-8"))
    results: list[dict] = []

    async with httpx.AsyncClient(
        timeout=30.0, follow_redirects=True, headers=HEADERS
    ) as client:
        for entry in data["sources"]:
            if not entry.get("is_active", True):
                continue
            district = entry.get("district_code")
            candidates: list[str] = []
            for base in (entry["url"], entry.get("fallback_url"), entry.get("registration_url")):
                if not base:
                    continue
                if "bendibao.com" in base:
                    candidates.extend(bendibao_variants(base))
                elif base not in candidates:
                    candidates.append(base)
            for news_url in NEWS_CANDIDATE_POOL:
                if news_url not in candidates:
                    candidates.append(news_url)

            row = {
                "type": "source",
                "name": entry["name"],
                "district_code": district,
                "url": entry["url"],
                "data_year": entry.get("data_year", expected_year),
            }
            for index, url in enumerate(candidates[:16]):
                if index > 0:
                    await asyncio.sleep(1.5)
                probe = await probe_url(client, url, district_code=district)
                row.update(
                    {
                        "url_tried": url,
                        "url_used": probe["url"],
                        "http_status": probe.get("http_status"),
                        "error": probe.get("error"),
                        "blocked": probe.get("blocked"),
                        "has_year": probe.get("has_year"),
                        "has_scope": probe.get("has_scope"),
                        "has_registration_time": probe.get("has_registration_time"),
                        "content_length": probe.get("content_length"),
                        "ok": probe.get("ok"),
                        "score": probe.get("score"),
                    }
                )
                if probe.get("ok"):
                    row["via"] = (
                        "fallback_url"
                        if url == entry.get("fallback_url")
                        else "registration_url"
                        if url == entry.get("registration_url")
                        else "mirror"
                        if url != entry["url"]
                        else "primary"
                    )
                    break

            if not row.get("ok"):
                row.setdefault("ok", False)
            results.append(row)
            await asyncio.sleep(1)

    return results


async def verify_schools(expected_year: int = POLICY_YEAR) -> list[dict]:
    schools = load_all_school_configs()
    results: list[dict] = []

    async with httpx.AsyncClient(
        timeout=20.0, follow_redirects=True, headers=HEADERS
    ) as client:
        for school in schools:
            website = (school.get("source_urls") or {}).get("website")
            row = {
                "type": "school",
                "name": school["name"],
                "district_code": school["district_code"],
                "data_year": school.get("data_year", expected_year),
                "verification_source": school.get("verification_source"),
                "website": website,
                "website_ok": None,
                "source_ok": None,
            }
            if website:
                status, _, err = await _fetch(client, website)
                row["website_ok"] = status is not None and status < 400
                row["website_status"] = status
                row["website_error"] = err
                await asyncio.sleep(0.5)
            vsrc = school.get("verification_source")
            if vsrc:
                status, text, err = await _fetch(client, vsrc)
                row["source_ok"] = (
                    status == 200
                    and "拼图验证" not in text
                    and str(expected_year) in text
                    and school["name"][:4] in text
                )
                row["source_status"] = status
                row["source_error"] = err
                # 名称未出现在页面时，仅要求页面含2026（登记点页可能以表格图片展示）
                if status == 200 and not row["source_ok"] and str(expected_year) in text:
                    row["source_ok"] = "拼图验证" not in text and len(text) > 800
                    row["source_name_on_page"] = False
                await asyncio.sleep(1)
            results.append(row)

    return results


def load_all_school_configs() -> list[dict]:
    data = yaml.safe_load(SCHOOLS_CONFIG.read_text(encoding="utf-8"))
    schools = list(data["schools"])
    for path in sorted(ROOT.glob(DISTRICT_SCHOOLS_GLOB)):
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        schools.extend(doc["schools"])
    return schools


def summarize_wuhou() -> dict:
    if not WUHOU_SCHOOLS.is_file():
        return {"available": False}
    doc = yaml.safe_load(WUHOU_SCHOOLS.read_text(encoding="utf-8"))
    schools = doc.get("schools", [])
    inventory = doc.get("inventory_summary", {})
    with_website = [
        s for s in schools if (s.get("source_urls") or {}).get("website")
    ]
    no_website = [
        s for s in schools if not (s.get("source_urls") or {}).get("website")
    ]
    verified_via = {"primary": 0, "alternate": 0}
    for s in schools:
        if s.get("inventory_status") != "verified":
            continue
        via = (s.get("source_urls") or {}).get("verification_via", "primary")
        verified_via[via] = verified_via.get(via, 0) + 1

    wuhou_report: dict = {}
    if WUHOU_VERIFY_REPORT.is_file():
        wuhou_report = json.loads(WUHOU_VERIFY_REPORT.read_text(encoding="utf-8"))

    failed_urls = []
    if wuhou_report.get("school_checks"):
        for name, row in wuhou_report["school_checks"].items():
            if not row.get("ok"):
                school = next((s for s in schools if s["name"] == name), {})
                failed_urls.append(
                    {
                        "name": name,
                        "website": (school.get("source_urls") or {}).get("website"),
                        "alternates": (school.get("source_urls") or {}).get(
                            "alternate_urls", []
                        ),
                    }
                )

    return {
        "available": True,
        "data_year": doc.get("data_year"),
        "inventory": inventory,
        "with_website": len(with_website),
        "no_website_enriched": len(no_website),
        "verified_via": verified_via,
        "last_verify": wuhou_report.get("verified_at"),
        "websites_ok": wuhou_report.get("websites_ok"),
        "verified_via_alternate": wuhou_report.get("verified_via_alternate"),
        "failed_website_checks": failed_urls[:20],
        "failed_website_count": len(failed_urls),
    }


async def main() -> int:
    expected_year = POLICY_YEAR
    if len(sys.argv) > 1:
        expected_year = int(sys.argv[1])

    source_results = await verify_sources(expected_year)
    school_results = await verify_schools(expected_year)

    report = {
        "verified_at": date.today().isoformat(),
        "data_year": expected_year,
        "sources": source_results,
        "schools": school_results,
        "districts": {
            "wuhou": summarize_wuhou(),
        },
        "summary": {
            "sources_ok": sum(1 for r in source_results if r.get("ok")),
            "sources_total": len(source_results),
            "schools_website_ok": sum(1 for r in school_results if r.get("website_ok")),
            "schools_with_website": sum(1 for r in school_results if r.get("website")),
            "schools_source_ok": sum(1 for r in school_results if r.get("source_ok")),
            "schools_total": len(school_results),
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report["districts"]["wuhou"].get("available"):
        print("\nwuhou:")
        print(json.dumps(report["districts"]["wuhou"], ensure_ascii=False, indent=2))
    print(f"report: {REPORT_PATH}")

    failed_sources = [r for r in source_results if not r.get("ok")]
    if failed_sources:
        print("\n未通过的政策源:")
        for r in failed_sources:
            print(f"  - {r['name']}: blocked={r.get('blocked')} year={r.get('has_year')}")

    return 0 if not failed_sources else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
