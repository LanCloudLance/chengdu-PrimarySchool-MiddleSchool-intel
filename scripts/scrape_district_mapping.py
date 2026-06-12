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

from chengdu_edu_parsers.mapping_parser import merge_promotion_links, parse_mapping_document

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
    if "cd.bendibao.com" in url:
        if "m.cd." not in url:
            candidates.insert(0, url.replace("://cd.", "://m.cd."))
        else:
            candidates.append(url.replace("://m.cd.", "://cd."))
    last_err: str | None = None
    best: tuple[str, str] | None = None
    for candidate in candidates:
        try:
            resp = client.get(candidate, follow_redirects=True)
            if "拼图验证" in resp.text:
                last_err = "captcha"
                continue
            if resp.status_code >= 400:
                last_err = f"http_{resp.status_code}"
                continue
            resolved = str(resp.url) if resp.url else candidate
            if len(resp.text) >= 5000:
                return resp.text, resolved
            if best is None or len(resp.text) > len(best[0]):
                best = (resp.text, resolved)
        except httpx.HTTPError as exc:
            last_err = str(exc)
    if best:
        return best
    return None, last_err


def scrape_district(
    client: httpx.Client,
    district_code: str,
    cfg: dict,
    *,
    promotion_only: bool = False,
    use_ocr: bool = False,
) -> dict:
    district_cfg = cfg["districts"].get(district_code, {})
    mapping_urls = [] if promotion_only else list(district_cfg.get("mapping_urls", []))
    all_urls = mapping_urls + list(district_cfg.get("promotion_urls", []))

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
        resolved_url = meta if isinstance(meta, str) and meta.startswith("http") else url
        kind = entry.get("kind", "unknown")
        parsed_promos = []
        parsed_scopes = []
        parsed_zones = []
        ocr_meta: dict = {}

        if kind == "promotion_table":
            try:
                from chengdu_edu_parsers.promotion_ocr import ocr_promotion_html

                ocr_result = ocr_promotion_html(html, client=client)
                parsed_promos = ocr_result.promotion_links
                ocr_meta = {
                    "ocr_lines": len(ocr_result.ocr_lines),
                    "ocr_errors": ocr_result.errors,
                }
            except RuntimeError as exc:
                errors.append(f"{url}: ocr_unavailable ({exc})")
        elif kind == "image_list" and use_ocr:
            try:
                from chengdu_edu_parsers.mapping_ocr import ocr_mapping_html

                ocr_result = ocr_mapping_html(html, client=client)
                parsed_scopes = ocr_result.school_scopes
                parsed_zones = []
                parsed_promos = []
                ocr_meta = {
                    "ocr_lines": len(ocr_result.ocr_lines),
                    "ocr_errors": ocr_result.errors,
                    "image_urls": len(ocr_result.image_urls),
                }
            except RuntimeError as exc:
                errors.append(f"{url}: ocr_unavailable ({exc})")
        else:
            parsed = parse_mapping_document(html, kind=kind if kind != "unknown" else "school_scope")
            parsed_scopes = parsed.school_scopes
            parsed_zones = parsed.zone_blocks
            parsed_promos = parsed.promotion_links

        article_row = {
            "url": resolved_url,
            "kind": kind,
            "scopes": len(parsed_scopes) if kind != "zone_list" else 0,
            "zones": len(parsed_zones),
            "promotions": len(parsed_promos),
            "data_year": entry.get("data_year", cfg.get("data_year", 2026)),
            "is_reference": entry.get("is_reference", False),
        }
        if ocr_meta:
            article_row["ocr"] = ocr_meta
        articles.append(article_row)

        if kind != "zone_list":
            scope_source = {
                "image_list": "ocr" if use_ocr else "html",
                "adjustment": "adjustment",
            }.get(kind, "html")
            for scope in parsed_scopes:
                row = asdict(scope) if hasattr(scope, "school_name") else dict(scope)
                row["source_url"] = resolved_url
                row["intel_year"] = entry.get("data_year", cfg.get("data_year", 2026))
                row["is_reference"] = entry.get("is_reference", False)
                row.setdefault("scope_source", scope_source)
                school_scopes.append(row)
        for zone in parsed_zones:
            zone = dict(zone)
            zone["source_url"] = resolved_url
            zone_blocks.append(zone)
        for link in parsed_promos:
            row = asdict(link)
            row["source_url"] = resolved_url
            row["intel_year"] = entry.get("data_year", cfg.get("data_year", 2026))
            row["is_reference"] = entry.get("is_reference", False)
            promotion_links.append(row)

    out_dir = ROOT / "configs" / "districts" / district_code
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "mapping_scraped.json"
    existing: dict = {}
    if out_path.is_file():
        existing = json.loads(out_path.read_text(encoding="utf-8"))

    if not school_scopes and existing.get("school_scopes"):
        school_scopes = list(existing["school_scopes"])
    if not zone_blocks and existing.get("zone_blocks"):
        zone_blocks = list(existing.get("zone_blocks") or [])

    from chengdu_edu_parsers.mapping_parser import PromotionLink, merge_scope_dicts

    merged_promos = merge_promotion_links(
        [
            PromotionLink(
                primary_name=row["primary_name"],
                target_names=row.get("target_names") or [],
                promotion_type=row.get("promotion_type", "对口直升"),
                source_excerpt=row.get("source_excerpt", ""),
            )
            for row in promotion_links
        ]
    )
    promotion_rows = [asdict(link) for link in merged_promos]

    payload = {
        "scraped_at": date.today().isoformat(),
        "district_code": district_code,
        "data_year": cfg.get("data_year", 2026),
        "school_scopes": merge_scope_dicts(school_scopes) if school_scopes else [],
        "zone_blocks": zone_blocks,
        "promotion_links": promotion_rows,
        "articles": (existing.get("articles") or []) + articles,
        "errors": (existing.get("errors") or []) + errors,
    }
    if existing.get("intel_synced"):
        payload["intel_synced"] = existing["intel_synced"]
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
    parser.add_argument(
        "--promotion-only",
        action="store_true",
        help="仅抓取 promotion_urls，保留已有 school_scopes",
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="对 image_list / promotion_table 源执行 OCR",
    )
    args = parser.parse_args()

    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    targets = CORE_DISTRICTS if args.all_core else (args.districts or ["gaoxin"])

    with httpx.Client(timeout=60, headers=HEADERS) as client:
        for code in targets:
            result = scrape_district(
                client,
                code,
                cfg,
                promotion_only=args.promotion_only,
                use_ocr=args.ocr,
            )
            print(
                f"{code}: scopes={result['scopes']} zones={result['zones']} "
                f"promotions={result['promotions']} errors={result['errors']} "
                f"-> {result['path']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
