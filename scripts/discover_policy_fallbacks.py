"""自动探测政策源 fallback_url，写回 configs/sources.yaml。"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

import yaml

from policy_url_utils import (
    DISTRICT_NEWS_FALLBACK,
    NEWS_CANDIDATE_POOL,
    bendibao_variants,
    find_best_policy_url,
    is_news_policy_url,
    is_registration_bendibao,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "configs" / "sources.yaml"
REPORT = ROOT / "configs" / "policy_discovery_report.json"


def load_sources() -> list[dict]:
    return yaml.safe_load(SOURCES.read_text(encoding="utf-8"))["sources"]


def save_sources(entries: list[dict]) -> None:
    doc = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    doc["sources"] = entries
    SOURCES.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def normalize_bendibao_path(url: str) -> str | None:
    if "bendibao.com" not in url:
        return None
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return parsed.path + (f"?{parsed.query}" if parsed.query else "")


async def discover_one(entry: dict, *, force: bool = False) -> dict:
    name = entry["name"]
    district = entry.get("district_code")
    existing = entry.get("fallback_url")
    primary_path = normalize_bendibao_path(entry["url"])
    candidates: list[str] = []

    preferred_news = DISTRICT_NEWS_FALLBACK.get(district or "")
    if preferred_news:
        candidates.append(preferred_news)
    if existing and is_news_policy_url(existing):
        candidates.append(existing)
    elif existing and not force:
        candidates.append(existing)
    if entry.get("url"):
        candidates.extend(bendibao_variants(entry["url"]))
    for news_url in NEWS_CANDIDATE_POOL:
        if news_url not in candidates:
            candidates.append(news_url)

    # 去掉与 primary 同路径的 bendibao 镜像；登记点页不作为 policy fallback
    filtered: list[str] = []
    for url in candidates:
        path = normalize_bendibao_path(url)
        if path and primary_path and path == primary_path:
            continue
        if is_registration_bendibao(url):
            continue
        if url not in filtered:
            filtered.append(url)

    best = await find_best_policy_url(filtered, district_code=district, max_probes=14)
    primary = await find_best_policy_url(
        bendibao_variants(entry["url"]),
        district_code=district,
        max_probes=6,
    )

    row = {
        "name": name,
        "district_code": district,
        "primary_url": entry["url"],
        "primary_ok": bool(primary and primary.get("ok")),
        "previous_fallback": existing,
        "discovered_fallback": None,
        "discovered_score": None,
        "updated": False,
        "status": "unchanged",
    }

    if best and best.get("ok"):
        chosen = best["url"]
        # news.chengdu.cn 优先于 bendibao 登记点/镜像页
        if preferred_news and is_news_policy_url(preferred_news):
            news_best = await find_best_policy_url(
                [preferred_news],
                district_code=district,
                max_probes=1,
            )
            if news_best and news_best.get("ok"):
                chosen = news_best["url"]
        row["discovered_fallback"] = chosen
        row["discovered_score"] = best.get("score")
        keep_existing = existing and (
            is_news_policy_url(existing)
            or (not force and existing == chosen)
        )
        if keep_existing and existing == chosen:
            row["status"] = "fallback_kept"
        elif keep_existing and is_news_policy_url(existing):
            entry["fallback_url"] = existing
            row["status"] = "fallback_kept"
        elif chosen != existing and chosen != entry.get("url"):
            entry["fallback_url"] = chosen
            row["updated"] = True
            row["status"] = "fallback_set"
        elif chosen == entry.get("url") and existing and existing != chosen:
            del entry["fallback_url"]
            row["updated"] = True
            row["status"] = "fallback_cleared"
        elif existing:
            row["status"] = "fallback_kept"
        else:
            entry["fallback_url"] = chosen
            row["updated"] = True
            row["status"] = "fallback_set"
    else:
        row["status"] = "not_found"

    return row


async def main() -> int:
    force = "--force" in sys.argv
    only_blocked = "--blocked-only" in sys.argv
    entries = load_sources()
    results: list[dict] = []
    updated = 0

    for entry in entries:
        if not entry.get("is_active", True):
            continue
        if only_blocked and entry.get("fallback_url"):
            # 仍探测无 fallback 或 primary 已知 blocked 的源
            pass
        result = await discover_one(entry, force=force)
        results.append(result)
        if result["updated"]:
            updated += 1
        print(
            f"{result['district_code']:8} {result['status']:14} "
            f"primary_ok={result['primary_ok']} "
            f"fallback={result.get('discovered_fallback') or '-'}"
        )

    if updated:
        save_sources(entries)

    report = {
        "discovered_at": date.today().isoformat(),
        "updated": updated,
        "results": results,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {REPORT} ({updated} sources updated)")
    return 0 if all(r["status"] != "not_found" for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
