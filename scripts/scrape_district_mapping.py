"""抓取各区划片/对口文章，缓存为 JSON。"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

import httpx
import yaml

from chengdu_edu_parsers.mapping_parser import parse_mapping_document

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "configs" / "district_mapping_sources.yaml"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

CORE_DISTRICTS = (
    "jinjiang",
    "qingyang",
    "wuhou",
    "chenghua",
    "jinniu",
    "gaoxin",
    "tianfu",
)


def fetch_url(client: httpx.Client, url: str) -> tuple[str | None, str | None]:
    candidates = [url]
    if "cd.bendibao.com" in url and not url.startswith("http://m."):
        candidates.insert(0, url.replace("://cd.", "://m.cd."))
    last_err: str | None = None
    for candidate in candidates:
        try:
            resp = client.get(candidate, follow_redirects=True)
            if "拼图验证" in resp.text:
                last_err = "captcha"
                continue
            if resp.status_code >= 400:
                last_err = f"http_{resp.status_code}"
                continue
            return resp.text, candidate
        except httpx.HTTPError as exc:
            last_err = str(exc)
    return None, last_err


def scrape_district(client: httpx.Client, district_code: str, cfg: dict) -> dict:
    district_cfg = cfg["districts"].get(district_code, {})
    all_urls = list(district_cfg.get("mapping_urls", [])) + list(
        district_cfg.get("promotion_urls", [])
    )

    school_scopes: list[dict] = []
    zone_blocks: list[dict] = []
    promotion_links: list[dict] = []
    articles: list[dict] = []
    errors: list[str] = []

    for entry in all_urls:
        url = entry["url"]
        time.sleep(1.2)
        html, meta = fetch_url(client, url)
        if html is None:
            errors.append(f"{url}: {meta}")
            continue
        parsed = parse_mapping_document(html)
        resolved_url = meta if isinstance(meta, str) and meta.startswith("http") else url
        kind = entry.get("kind", "unknown")
        articles.append(
            {
                "url": resolved_url,
                "kind": kind,
                "scopes": len(parsed.school_scopes) if kind != "zone_list" else 0,
                "zones": len(parsed.zone_blocks),
                "promotions": len(parsed.promotion_links),
            }
        )
        if kind != "zone_list":
            for scope in parsed.school_scopes:
                row = asdict(scope)
                row["source_url"] = resolved_url
                school_scopes.append(row)
        for zone in parsed.zone_blocks:
            zone = dict(zone)
            zone["source_url"] = resolved_url
            zone_blocks.append(zone)
        for link in parsed.promotion_links:
            row = asdict(link)
            row["source_url"] = resolved_url
            promotion_links.append(row)

    out_dir = ROOT / "configs" / "districts" / district_code
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "mapping_scraped.json"
    payload = {
        "scraped_at": date.today().isoformat(),
        "district_code": district_code,
        "data_year": cfg.get("data_year", 2026),
        "school_scopes": school_scopes,
        "zone_blocks": zone_blocks,
        "promotion_links": promotion_links,
        "articles": articles,
        "errors": errors,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(out_path),
        "scopes": len(school_scopes),
        "zones": len(zone_blocks),
        "promotions": len(promotion_links),
        "errors": len(errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape district mapping articles")
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    args = parser.parse_args()

    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    targets = CORE_DISTRICTS if args.all_core else (args.districts or ["gaoxin"])

    with httpx.Client(timeout=30, headers=HEADERS) as client:
        for code in targets:
            result = scrape_district(client, code, cfg)
            print(
                f"{code}: scopes={result['scopes']} zones={result['zones']} "
                f"promotions={result['promotions']} errors={result['errors']} "
                f"-> {result['path']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
