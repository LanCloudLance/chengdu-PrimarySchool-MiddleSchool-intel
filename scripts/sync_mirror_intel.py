"""将 scraped_mirrors.json 中的本地宝 mirror 页同步到 intel_entries（MIRROR_PAGE）。"""
from __future__ import annotations

import argparse
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup
from sqlalchemy import select

from chengdu_edu_core.enums import IntelType
from chengdu_edu_core.hashing import content_hash
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.intel_repository import IntelRepository
from chengdu_edu_storage.orm import District, School

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}


def load_mirror_map(district_code: str) -> dict[str, str]:
    path = ROOT / "configs" / "districts" / district_code / "scraped_mirrors.json"
    if not path.is_file():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return dict(doc.get("mirrors") or {})


def load_inventory_mirror_map(district_code: str) -> dict[str, str]:
    """从 schools.yaml 已验收的 verification_url / mirror_urls 构建 mirror 映射。"""
    path = ROOT / "configs" / "districts" / district_code / "schools.yaml"
    if not path.is_file():
        return {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mirrors: dict[str, str] = {}
    for school in doc.get("schools") or []:
        name = school.get("name")
        if not name:
            continue
        urls = school.get("source_urls") or {}
        for key in ("verification_url",):
            url = urls.get(key)
            if url and "wangdian" in url:
                mirrors.setdefault(name, url)
        for url in urls.get("mirror_urls") or []:
            if url and "wangdian" in url:
                mirrors.setdefault(name, url)
    return mirrors


def page_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    return soup.title.string.strip() if soup.title and soup.title.string else None


def fetch_html(client: httpx.Client, url: str) -> tuple[str | None, str | None]:
    candidates = [url]
    if "cd.bendibao.com" in url:
        if "m.cd." not in url:
            candidates.insert(0, url.replace("://cd.", "://m.cd."))
    last_err: str | None = None
    for candidate in candidates:
        try:
            resp = client.get(candidate, follow_redirects=True)
            if "拼图验证" in resp.text:
                last_err = "captcha"
                continue
            if resp.status_code >= 400 or len(resp.text) < 300:
                last_err = f"http_{resp.status_code}"
                continue
            resolved = str(resp.url) if resp.url else candidate
            return resp.text, resolved
        except httpx.HTTPError as exc:
            last_err = str(exc)
    return None, last_err


async def _school_name_map(session, district_id) -> dict[str, str]:
    schools = (
        await session.execute(select(School).where(School.district_id == district_id))
    ).scalars().all()
    return {school.name: str(school.id) for school in schools}


def _fetch_mirror_row(school_name: str, mirror_url: str) -> tuple[dict | None, str | None]:
    with httpx.Client(timeout=12, headers=HEADERS) as client:
        html, meta = fetch_html(client, mirror_url)
    if html is None:
        return None, f"{school_name}: {meta}"
    resolved = meta if isinstance(meta, str) and meta.startswith("http") else mirror_url
    return {
        "school_name": school_name,
        "source_url": resolved,
        "content_hash": content_hash(html),
        "source_title": page_title(html),
        "raw_html_len": len(html),
    }, None


async def sync_district_mirrors(
    session,
    district_code: str,
    *,
    limit: int | None = None,
    skip_db: bool = False,
    workers: int = 6,
    from_inventory: bool = False,
) -> dict:
    mirrors = load_inventory_mirror_map(district_code) if from_inventory else load_mirror_map(district_code)
    if not mirrors:
        return {"synced": 0, "skipped": 0, "errors": 1, "reason": "no_mirrors_file"}

    district = None
    name_to_id: dict[str, str] = {}
    repo = None
    if not skip_db:
        district = (
            await session.execute(select(District).where(District.code == district_code))
        ).scalar_one_or_none()
        if district is None:
            return {"synced": 0, "skipped": 0, "errors": 1, "reason": "unknown_district"}
        name_to_id = await _school_name_map(session, district.id)
        repo = IntelRepository(session)
    data_year = int(
        yaml.safe_load(
            (ROOT / "configs" / "district_mapping_sources.yaml").read_text(encoding="utf-8")
        ).get("data_year", 2025)
    )

    synced = 0
    skipped = 0
    errors: list[str] = []
    entries: list[dict] = []
    items = list(mirrors.items())
    if limit:
        items = items[:limit]

    fetched: list[dict] = []
    if from_inventory:
        for school_name, mirror_url in items:
            fetched.append(
                {
                    "school_name": school_name,
                    "source_url": mirror_url,
                    "content_hash": content_hash(f"inventory-mirror:{school_name}:{mirror_url}"),
                    "source_title": school_name,
                    "raw_html_len": 0,
                    "from_inventory": True,
                }
            )
    else:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(_fetch_mirror_row, school_name, mirror_url): school_name
                for school_name, mirror_url in items
            }
            for future in as_completed(futures):
                row, err = future.result()
                if err:
                    errors.append(err)
                    continue
                fetched.append(row)

    for row in fetched:
        school_name = row["school_name"]
        school_id = name_to_id.get(school_name)
        row["school_id"] = school_id
        entries.append(row)

        if repo is None:
            synced += 1
            continue

        if school_id is None:
            errors.append(f"{school_name}: school_not_in_inventory")
            continue

        digest = row["content_hash"]
        resolved = row["source_url"]
        title = row["source_title"]
        existing = await repo.find_by_hash(digest)
        if (
            existing
            and existing.source_url == resolved
            and existing.content_hash == digest
            and existing.school_id
            and str(existing.school_id) == school_id
        ):
            skipped += 1
            continue

        await repo.upsert_entry(
            district_id=district.id,  # type: ignore[union-attr]
            school_id=school_id,
            intel_type=IntelType.MIRROR_PAGE,
            source_url=resolved,
            source_title=title,
            content_hash=digest,
            raw_text=None,
            structured_fields={
                "school_name": school_name,
                "mirror_url": resolved,
                "page_title": title,
                "raw_html_len": row.get("raw_html_len"),
            },
            data_year=data_year,
            is_reference=True,
        )
        synced += 1

    manifest = {
        "synced_at": date.today().isoformat(),
        "district_code": district_code,
        "mirror_targets": len(mirrors),
        "processed": len(items),
        "synced": synced,
        "skipped": skipped,
        "errors": errors,
        "entries": entries,
        "skip_db": skip_db,
        "from_inventory": from_inventory,
    }
    out_path = ROOT / "configs" / "districts" / district_code / "mirror_intel_manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "synced": synced,
        "skipped": skipped,
        "errors": len(errors),
        "manifest": str(out_path),
        "targets": len(mirrors),
    }


async def run_sync(
    districts: list[str],
    *,
    limit: int | None = None,
    manifest_only: bool = False,
    workers: int = 6,
    from_inventory: bool = False,
) -> None:
    if manifest_only:
        for code in districts:
            result = await sync_district_mirrors(
                None,
                code,
                limit=limit,
                skip_db=True,
                workers=workers,
                from_inventory=from_inventory,
            )
            _print_mirror_result(code, result)
        return

    async with SessionLocal() as session:
        for code in districts:
            result = await sync_district_mirrors(
                session,
                code,
                limit=limit,
                skip_db=False,
                workers=workers,
                from_inventory=from_inventory,
            )
            _print_mirror_result(code, result)


def _print_mirror_result(code: str, result: dict) -> None:
    print(
        f"{code}: synced={result.get('synced', 0)} "
        f"skipped={result.get('skipped', 0)} "
        f"errors={result.get('errors', 0)} "
        f"targets={result.get('targets', 0)} "
        f"-> {result.get('manifest', result.get('reason', ''))}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync bendibao mirror pages to intel_entries")
    parser.add_argument("--district", action="append", dest="districts")
    parser.add_argument("--limit", type=int, help="仅处理前 N 条 mirror（调试用）")
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="仅写 mirror_intel_manifest.json，不入库（无 DB 时验收用）",
    )
    parser.add_argument("--workers", type=int, default=6, help="并行抓取线程数")
    parser.add_argument(
        "--from-inventory",
        action="store_true",
        help="用 schools.yaml 已验收 mirror URL 写 manifest（免抓取，防 captcha）",
    )
    args = parser.parse_args()
    districts = args.districts or ["wuhou"]
    asyncio.run(
        run_sync(
            districts,
            limit=args.limit,
            manifest_only=args.manifest_only,
            workers=args.workers,
            from_inventory=args.from_inventory,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
