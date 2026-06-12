"""同步情报库：抓取配置源 → 本地 intel_entries 持久化（hash 去重，门户只读库）。"""
from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup
from sqlalchemy import select

from chengdu_edu_core.enums import IntelType
from chengdu_edu_core.hashing import content_hash
from chengdu_edu_parsers.mapping_parser import (
    extract_bendibao_content_images,
    merge_scope_dicts,
    parse_mapping_document,
)
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.intel_repository import IntelRepository
from chengdu_edu_storage.orm import District, EnrollmentPolicy, RawDocument
from chengdu_edu_core.enums import PolicyType

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


def fetch_html(client: httpx.Client, url: str) -> tuple[str | None, str | None]:
    candidates = [url]
    if "cd.bendibao.com" in url:
        if "m.cd." not in url:
            candidates.insert(0, url.replace("://cd.", "://m.cd."))
        candidates.append(url.replace("://m.cd.", "://cd."))
    last_err: str | None = None
    for candidate in candidates:
        try:
            resp = client.get(candidate, follow_redirects=True)
            if "拼图验证" in resp.text:
                last_err = "captcha"
                continue
            if resp.status_code >= 400 or len(resp.text) < 500:
                last_err = f"http_{resp.status_code}"
                continue
            return resp.text, candidate
        except httpx.HTTPError as exc:
            last_err = str(exc)
    return None, last_err


def page_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    return soup.title.string.strip() if soup.title and soup.title.string else None


async def sync_gov_intel(session, district_code: str, district_id) -> int:
    stmt = (
        select(EnrollmentPolicy, RawDocument)
        .join(District, EnrollmentPolicy.district_id == District.id)
        .outerjoin(RawDocument, RawDocument.id == EnrollmentPolicy.source_doc_id)
        .where(
            District.code == district_code,
            EnrollmentPolicy.school_id.is_(None),
            EnrollmentPolicy.policy_type == PolicyType.GOV_POLICY,
        )
        .order_by(EnrollmentPolicy.year.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        return 0
    policy, doc = row
    text = (doc.raw_content if doc and doc.raw_content else "") or ""
    if len(text) < 200:
        return 0

    repo = IntelRepository(session)
    source_url = doc.raw_file_path or f"gov_policy:{district_code}"
    await repo.upsert_entry(
        district_id=district_id,
        school_id=None,
        intel_type=IntelType.GOV_ARTICLE,
        source_url=source_url,
        source_title=f"{district_code} gov_policy {policy.year}",
        content_hash=content_hash(text),
        raw_text=text[:500_000],
        structured_fields={"policy_year": policy.year, "fields": policy.fields},
        data_year=policy.year,
        is_reference=False,
    )
    return 1


async def sync_district_mapping_sources(
    client: httpx.Client,
    session,
    district_code: str,
    district_id,
    cfg: dict,
    *,
    use_ocr: bool = False,
) -> dict:
    district_cfg = cfg["districts"].get(district_code, {})
    urls = list(district_cfg.get("mapping_urls", []))
    repo = IntelRepository(session)

    school_scopes: list[dict] = []
    zone_blocks: list[dict] = []
    articles: list[dict] = []
    errors: list[str] = []
    intel_saved = 0
    skipped = 0

    for entry in urls:
        url = entry["url"]
        kind = entry.get("kind", "school_scope")
        data_year = entry.get("data_year", cfg.get("data_year", 2026))
        is_reference = entry.get("is_reference", data_year < cfg.get("data_year", 2026))

        time.sleep(1.0)
        html, meta = fetch_html(client, url)
        if html is None:
            errors.append(f"{url}: {meta}")
            continue

        resolved = meta if isinstance(meta, str) and meta.startswith("http") else url
        digest = content_hash(html)
        existing = await repo.find_by_hash(digest)

        image_urls: list[str] = []
        ocr_meta: dict = {}
        if kind == "image_list":
            image_urls = extract_bendibao_content_images(html)
            parsed_scopes = []
            parsed_zones = []
            if use_ocr:
                try:
                    from chengdu_edu_parsers.mapping_ocr import ocr_mapping_html

                    ocr_result = ocr_mapping_html(html, client=client)
                    if ocr_result.image_urls:
                        image_urls = ocr_result.image_urls
                    parsed_scopes = [asdict(s) for s in ocr_result.school_scopes]
                    ocr_meta = {
                        "ocr_lines": len(ocr_result.ocr_lines),
                        "ocr_errors": ocr_result.errors,
                    }
                except RuntimeError as exc:
                    errors.append(f"{url}: ocr_unavailable ({exc})")
        else:
            parsed = parse_mapping_document(html, kind=kind)
            parsed_scopes = [asdict(s) for s in parsed.school_scopes]
            parsed_zones = parsed.zone_blocks
            if kind == "zone_list":
                parsed_scopes = []

        scope_source = {
            "school_scope": "html",
            "image_list": "ocr",
            "adjustment": "adjustment",
            "zone_list": "html",
        }.get(kind, "html")
        for scope in parsed_scopes:
            scope["source_url"] = resolved
            scope["intel_year"] = data_year
            scope["is_reference"] = is_reference
            scope["scope_source"] = scope_source
        for zone in parsed_zones:
            zone["source_url"] = resolved

        structured = {
            "kind": kind,
            "school_scopes": parsed_scopes,
            "zone_blocks": parsed_zones,
            "image_urls": image_urls,
            **ocr_meta,
        }
        if existing and existing.source_url == resolved and existing.content_hash == digest:
            if existing.structured_fields == structured:
                skipped += 1
            else:
                intel_saved += 1
        else:
            intel_saved += 1

        await repo.upsert_entry(
            district_id=district_id,
            school_id=None,
            intel_type=IntelType.MAPPING,
            source_url=resolved,
            source_title=page_title(html),
            content_hash=digest,
            raw_text=html[:800_000],
            structured_fields=structured,
            data_year=data_year,
            is_reference=is_reference,
        )

        article_row = {
            "url": resolved,
            "kind": kind,
            "scopes": len(parsed_scopes),
            "zones": len(parsed_zones),
            "data_year": data_year,
            "is_reference": is_reference,
        }
        if ocr_meta:
            article_row["ocr"] = ocr_meta
        articles.append(article_row)
        if kind != "zone_list":
            school_scopes.extend(parsed_scopes)
        zone_blocks.extend(parsed_zones)

    school_scopes = merge_scope_dicts(school_scopes)

    # 镜像 JSON 缓存（兼容旧 import 脚本）
    out_dir = ROOT / "configs" / "districts" / district_code
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "mapping_scraped.json"
    payload = {
        "scraped_at": date.today().isoformat(),
        "district_code": district_code,
        "data_year": cfg.get("data_year", 2026),
        "school_scopes": school_scopes,
        "zone_blocks": zone_blocks,
        "articles": articles,
        "errors": errors,
        "intel_synced": True,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    gov_saved = await sync_gov_intel(session, district_code, district_id)

    return {
        "intel_saved": intel_saved,
        "skipped": skipped,
        "scopes": len(school_scopes),
        "gov": gov_saved,
        "errors": len(errors),
        "path": str(out_path),
    }


async def run_sync(districts: list[str], *, use_ocr: bool = False) -> None:
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    async with SessionLocal() as session:
        code_map = {
            d.code: d.id
            for d in (await session.execute(select(District))).scalars().all()
        }
        with httpx.Client(timeout=40, headers=HEADERS) as client:
            for code in districts:
                if code not in code_map:
                    print(f"skip unknown district: {code}")
                    continue
                result = await sync_district_mapping_sources(
                    client, session, code, code_map[code], cfg, use_ocr=use_ocr
                )
                print(
                    f"{code}: intel_saved={result['intel_saved']} skipped={result['skipped']} "
                    f"scopes={result['scopes']} gov={result['gov']} errors={result['errors']}"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync intel library from configured sources")
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--all-core", action="store_true")
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="对 image_list 源执行 PNG OCR 试点解析",
    )
    args = parser.parse_args()
    targets = CORE_DISTRICTS if args.all_core else (args.districts or ["wuhou"])
    asyncio.run(run_sync(targets, use_ocr=args.ocr))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
