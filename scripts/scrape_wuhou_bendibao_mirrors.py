"""从本地宝武侯学校列表页抓取校名->详情页 mirror，写入 scraped_mirrors.json。"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import date
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS_YAML = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
OUT_JSON = ROOT / "configs" / "districts" / "wuhou" / "scraped_mirrors.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "zh-CN,zh;q=0.9",
}

LIST_URLS = [
    "https://cd.bendibao.com/edu/xiaoxuelist/wuhouqu/gongban/",
    "https://m.cd.bendibao.com/edu/xiaoxuelist/wuhouqu/gongban/",
    "https://cd.bendibao.com/edu/xiaoxuelist/wuhouqu/minban/",
    "https://m.cd.bendibao.com/edu/xiaoxuelist/wuhouqu/minban/",
    "https://cd.bendibao.com/edu/chuzhonglist/wuhouqu/gongban/",
    "https://m.cd.bendibao.com/edu/chuzhonglist/wuhouqu/gongban/",
    "https://cd.bendibao.com/edu/chuzhonglist/wuhouqu/minban/",
    "https://m.cd.bendibao.com/edu/chuzhonglist/wuhouqu/minban/",
]


def clean_name(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"(公办|民办)(武侯区|成都市)?$", "", raw)
    if not raw.startswith(("成都", "四川", "北京")):
        raw = f"成都市{raw}"
    return raw


def scrape_list(base: str, *, page_delay: float = 14.0) -> tuple[dict[str, str], str | None]:
    found: dict[str, str] = {}
    blocked: str | None = None
    with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
        for page in range(1, 7):
            url = base if page == 1 else f"{base}?page={page}"
            if page > 1:
                time.sleep(page_delay)
            resp = client.get(url)
            if "拼图验证" in resp.text:
                blocked = url
                break
            soup = BeautifulSoup(resp.text, "html.parser")
            items = soup.select("div.school_item")
            if not items:
                break
            for card in items:
                name_div = card.select_one("div.name")
                link = card.select_one('a[href*="wangdian"]')
                if not name_div or not link:
                    continue
                name = clean_name(name_div.get_text(strip=True))
                href = link["href"]
                if not href.startswith("http"):
                    href = "https://cd.bendibao.com" + href
                found[name] = href
            if len(items) < 15:
                break
    return found, blocked


def main() -> int:
    target_names = {
        s["name"]
        for s in yaml.safe_load(SCHOOLS_YAML.read_text(encoding="utf-8"))["schools"]
    }
    mirrors: dict[str, str] = {}
    blocked_lists: list[str] = []
    errors: list[str] = []
    list_errors: list[str] = []

    for list_url in LIST_URLS:
        time.sleep(14)
        try:
            batch, blocked = scrape_list(list_url)
        except httpx.HTTPError as exc:
            list_errors.append(f"{list_url}: {exc}")
            continue
        if blocked:
            blocked_lists.append(blocked)
            continue
        for name, url in batch.items():
            if name in target_names:
                mirrors[name] = url

    doc = {
        "scraped_at": date.today().isoformat(),
        "mirrors": mirrors,
        "matched": len(mirrors),
        "targets": len(target_names),
        "blocked_lists": blocked_lists,
        "errors": errors,
        "list_errors": list_errors,
    }
    OUT_JSON.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"wrote {OUT_JSON}: matched {len(mirrors)}/{len(target_names)}, "
        f"blocked {len(blocked_lists)}, errors {len(errors)}"
    )
    return 0 if mirrors else 1


if __name__ == "__main__":
    raise SystemExit(main())
