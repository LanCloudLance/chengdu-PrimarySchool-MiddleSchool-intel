"""从本地宝武侯区学校大全抓取清单，生成 configs/districts/wuhou/schools.yaml。"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "configs" / "districts" / "wuhou"
RAW_JSON = ROOT / "configs" / "districts" / "wuhou_inventory_raw.json"
OUT_YAML = OUT_DIR / "schools.yaml"
ENRICHMENT_YAML = OUT_DIR / "enrichment.yaml"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

LIST_URLS = {
    "public_primary": "https://cd.bendibao.com/edu/xiaoxuelist/wuhouqu/gongban/",
    "private_primary": "https://cd.bendibao.com/edu/xiaoxuelist/wuhouqu/minban/",
    "public_middle": "https://cd.bendibao.com/edu/chuzhonglist/wuhouqu/gongban/",
    "private_middle": "https://cd.bendibao.com/edu/chuzhonglist/wuhouqu/minban/",
}

TYPE_LEVEL = {
    "public_primary": ("public", "primary"),
    "private_primary": ("private", "primary"),
    "public_middle": ("public", "middle"),
    "private_middle": ("private", "middle"),
}

REGISTRATION_URL = "http://cd.bendibao.com/edu/2026424/207396.shtm"
POLICY_URL = "http://cd.bendibao.com/edu/2026417/207074.shtm"
DATA_YEAR = 2026

# 本地宝目录未收录、但需保留的代表性学校（待补地址/电话）
MANUAL_SCHOOLS: list[dict] = [
    {
        "name": "成都市洗面桥小学",
        "address": "成都市武侯区洗面桥横街28号",
        "phone": None,
        "category": "public_primary",
    },
    {
        "name": "成都市玉林中学",
        "address": "成都市武侯区倪家桥路12号",
        "phone": None,
        "category": "public_middle",
    },
]


def clean_name(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"(公办|民办)(武侯区|成都市)?$", "", raw)
    if not raw.startswith(("成都", "四川", "北京")):
        raw = f"成都市{raw}"
    return raw.strip()


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows: list[dict] = []
    for card in soup.select("div.school_item"):
        name_div = card.select_one("div.name")
        if not name_div:
            continue
        name = clean_name(name_div.get_text(strip=True))
        address = phone = None
        ul = card.select_one("ul.info_ul")
        if ul:
            for li in ul.find_all("li"):
                parts = li.find_all("div")
                if len(parts) < 2:
                    continue
                label = parts[0].get_text(strip=True)
                value = parts[1].get_text(strip=True)
                if "地址" in label and value not in ("无更新", ""):
                    address = value.replace("\n", " / ")
                if "电话" in label and value not in ("无更新", ""):
                    phone = value.replace("\n", " / ")
        rows.append({"name": name, "address": address, "phone": phone})
    return rows


def fetch_category(url: str, *, max_pages: int = 6) -> list[dict]:
    collected: list[dict] = []
    for page in range(1, max_pages + 1):
        page_url = url if page == 1 else f"{url}?page={page}"
        for attempt in range(4):
            if page > 1 or attempt > 0:
                time.sleep(12)
            resp = httpx.get(
                page_url, headers=HEADERS, timeout=30, follow_redirects=True
            )
            if "拼图验证" not in resp.text:
                break
            time.sleep(20)
        else:
            break
        items = parse_page(resp.text)
        if not items:
            break
        collected.extend(items)
        if len(items) < 15:
            break
    return collected


def normalize_address(addr: str | None) -> str:
    if not addr:
        return ""
    return re.sub(r"\s+", "", addr)


def dedupe_rows(rows: list[dict]) -> list[dict]:
    by_addr: dict[str, dict] = {}
    no_addr: list[dict] = []
    for row in rows:
        addr_key = normalize_address(row.get("address"))
        if not addr_key:
            no_addr.append(row)
            continue
        existing = by_addr.get(addr_key)
        if existing is None or len(row["name"]) > len(existing["name"]):
            by_addr[addr_key] = row
    out = list(by_addr.values()) + no_addr
    out.sort(key=lambda r: r["name"])
    return out


def short_name(full: str) -> str:
    for prefix in ("成都市", "成都", "四川", "北京第二外国语学院"):
        if full.startswith(prefix):
            return full[len(prefix) :].strip("（）()")
    return full


def load_enrichment() -> dict:
    if not ENRICHMENT_YAML.is_file():
        return {"websites": {}, "group_websites": [], "verified_websites": []}
    data = yaml.safe_load(ENRICHMENT_YAML.read_text(encoding="utf-8")) or {}
    data.setdefault("websites", {})
    data.setdefault("group_websites", [])
    data.setdefault("verified_websites", [])
    data.setdefault("no_website", {})
    data.setdefault("drop_duplicates", [])
    return data


def resolve_website(name: str, enrichment: dict) -> tuple[str | None, str | None]:
    exact = enrichment["websites"].get(name)
    if exact:
        return exact, None
    for group in enrichment["group_websites"]:
        prefix = group["prefix"]
        if name.startswith(prefix):
            return group["website"], group.get("note")
    return None, None


def apply_no_website(schools: list[dict], enrichment: dict) -> None:
    entries = enrichment.get("no_website") or {}
    for school in schools:
        entry = entries.get(school["name"])
        if not entry:
            continue
        school["inventory_status"] = "enriched"
        school["enrichment_note"] = entry.get("reason")
        if entry.get("researched_at"):
            school["enrichment_resolved_at"] = entry["researched_at"]
        urls = dict(school.get("source_urls") or {})
        urls.pop("website", None)
        urls.pop("group_website", None)
        urls.pop("group_note", None)
        if entry.get("channel"):
            urls["contact_channel"] = entry["channel"]
        school["source_urls"] = urls
        school["verified"] = False


def apply_mirror_urls(schools: list[dict], enrichment: dict) -> None:
    from wuhou_url_utils import collect_alternate_urls

    no_website = set((enrichment.get("no_website") or {}).keys())
    for school in schools:
        if school["name"] not in no_website:
            continue
        alternates = collect_alternate_urls(
            primary=None,
            school_name=school["name"],
            enrichment=enrichment,
        )
        if not alternates:
            continue
        urls = dict(school.get("source_urls") or {})
        urls["mirror_urls"] = [a["url"] for a in alternates]
        school["source_urls"] = urls


def apply_alternates(schools: list[dict], enrichment: dict) -> None:
    from wuhou_url_utils import collect_alternate_urls

    for school in schools:
        urls = school.get("source_urls") or {}
        primary = urls.get("website")
        if not primary:
            continue
        alternates = collect_alternate_urls(
            primary=primary,
            school_name=school["name"],
            enrichment=enrichment,
        )
        if alternates:
            urls = dict(urls)
            urls["alternate_urls"] = [a["url"] for a in alternates]
            school["source_urls"] = urls


def apply_enrichment(schools: list[dict], enrichment: dict) -> None:
    verified_urls = set(enrichment.get("verified_websites") or [])
    for school in schools:
        website, group_note = resolve_website(school["name"], enrichment)
        if not website:
            continue
        urls = dict(school.get("source_urls") or {})
        urls["website"] = website
        if group_note:
            urls["group_website"] = website
            urls["group_note"] = group_note
        school["source_urls"] = urls
        resolved = urls.get("verification_url") or urls.get("website_resolved")
        if website in verified_urls or (resolved and resolved in verified_urls):
            school["verified"] = True
            school["inventory_status"] = "verified"
        else:
            school["inventory_status"] = "enriched"


def merge_prior_verification(schools: list[dict]) -> None:
    if not OUT_YAML.is_file():
        return
    prior = {
        s["name"]: s
        for s in yaml.safe_load(OUT_YAML.read_text(encoding="utf-8")).get("schools", [])
    }
    for school in schools:
        old = prior.get(school["name"])
        if not old or old.get("inventory_status") != "verified":
            continue
        school["inventory_status"] = "verified"
        school["verified"] = True
        if old.get("verified_at"):
            school["verified_at"] = old["verified_at"]
        old_urls = old.get("source_urls") or {}
        urls = dict(school.get("source_urls") or {})
        for key in (
            "verification_url",
            "verification_via",
            "website_resolved",
            "alternate_urls",
            "mirror_urls",
        ):
            if old_urls.get(key):
                urls[key] = old_urls[key]
        school["source_urls"] = urls


def dedupe_schools(schools: list[dict], enrichment: dict) -> list[dict]:
    drop = set(enrichment.get("drop_duplicates") or [])
    if not drop:
        return schools
    return [s for s in schools if s["name"] not in drop]


def to_school_rows(inventory: dict[str, list[dict]], enrichment: dict) -> list[dict]:
    schools: list[dict] = []
    for category, rows in inventory.items():
        school_type, level = TYPE_LEVEL[category]
        for row in dedupe_rows(rows):
            name = row["name"]
            website, _ = resolve_website(name, enrichment)
            status = "enriched" if website else "listed"
            entry: dict = {
                "name": name,
                "short_name": short_name(name)[:20] or None,
                "district_code": "wuhou",
                "type": school_type,
                "level": level,
                "address": row.get("address"),
                "data_year": DATA_YEAR,
                "inventory_status": status,
                "verified": False,
                "verification_source": LIST_URLS[category],
                "list_category": category,
            }
            if row.get("phone"):
                entry["phone"] = row["phone"]
            if website:
                entry["source_urls"] = {"website": website}
            if category.endswith("_primary"):
                entry["role"] = "registration_point_candidate"
            schools.append(entry)
    schools.sort(key=lambda s: (s["level"], s["type"], s["name"]))
    return schools


def scrape_inventory() -> dict[str, list[dict]]:
    inv: dict[str, list[dict]] = {}
    for category, url in LIST_URLS.items():
        time.sleep(15)
        inv[category] = fetch_category(url)
        print(f"{category}: {len(inv[category])}")
    RAW_JSON.parent.mkdir(parents=True, exist_ok=True)
    RAW_JSON.write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    return inv


def load_or_scrape() -> dict[str, list[dict]]:
    if RAW_JSON.is_file() and "--refresh" not in sys.argv:
        inv = json.loads(RAW_JSON.read_text(encoding="utf-8"))
    else:
        inv = scrape_inventory()
    existing = {row["name"] for rows in inv.values() for row in rows}
    for manual in MANUAL_SCHOOLS:
        if manual["name"] in existing:
            continue
        category = manual["category"]
        inv.setdefault(category, []).append(
            {
                "name": manual["name"],
                "address": manual.get("address"),
                "phone": manual.get("phone"),
            }
        )
    return inv


def main() -> None:
    enrichment = load_enrichment()
    inventory = load_or_scrape()
    schools = to_school_rows(inventory, enrichment)
    apply_enrichment(schools, enrichment)
    apply_no_website(schools, enrichment)
    apply_mirror_urls(schools, enrichment)
    apply_alternates(schools, enrichment)
    merge_prior_verification(schools)
    schools = dedupe_schools(schools, enrichment)
    counts = {k: len(v) for k, v in inventory.items()}
    doc = {
        "district_code": "wuhou",
        "data_year": DATA_YEAR,
        "notes": (
            "武侯区学校清单：公办/民办 小学+初中。"
            "名单来源本地宝学校大全（2026-06 抓取）；"
            "登记点以 4 月 edu 公告为准，划片以 6 月 15 日 yjrx 平台为准。"
        ),
        "sources": {
            "registration_guide": REGISTRATION_URL,
            "policy": POLICY_URL,
            **LIST_URLS,
        },
        "counts": counts,
        "inventory_summary": {
            "total": len(schools),
            "listed": sum(1 for s in schools if s["inventory_status"] == "listed"),
            "enriched": sum(1 for s in schools if s["inventory_status"] == "enriched"),
            "verified": sum(
                1 for s in schools if s.get("inventory_status") == "verified"
            ),
        },
        "schools": schools,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_YAML.write_text(
        yaml.safe_dump(doc, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    print(f"wrote {OUT_YAML} ({len(schools)} schools)")


if __name__ == "__main__":
    main()
