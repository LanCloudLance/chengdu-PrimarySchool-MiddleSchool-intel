"""从本地宝 mirror 映射同步 enrichment.yaml 的 alternate_urls。"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ENRICHMENT = ROOT / "configs" / "districts" / "wuhou" / "enrichment.yaml"
SCHOOLS = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
SCRAPED = ROOT / "configs" / "districts" / "wuhou" / "scraped_mirrors.json"

# 校名 -> 本地宝详情页（优先于 primary 级 mirror；ID 经 title 校验）
BENDIBAO_BY_NAME: dict[str, str] = {
    "成都市龙江路小学": "https://m.cd.bendibao.com/wangdian/dian/5432806.shtm",
    "成都市龙江路小学（南区）": "https://m.cd.bendibao.com/wangdian/dian/5434420.shtm",
    "成都市龙江路小学分校": "https://m.cd.bendibao.com/wangdian/dian/5432807.shtm",
    "成都市龙江路小学分校南区学校": "https://m.cd.bendibao.com/wangdian/dian/93684.shtm",
    "成都市龙江路小学武侯新城分校": "https://cd.bendibao.com/wangdian/dian/5433887.shtm",
    "成都市龙江路小学武侯新城分校南区学校": "https://m.cd.bendibao.com/wangdian/dian/5436423.shtm",
    "成都市龙江路小学中粮祥云分校": "https://m.cd.bendibao.com/wangdian/dian/5433326.shtm",
    "成都市龙江路小学高翔分校": "https://m.cd.bendibao.com/wangdian/dian/5868269.shtm",
    "四川大学附属实验小学": "https://m.cd.bendibao.com/wangdian/dian/5432822.shtm",
    "四川大学附属实验小学分校": "https://m.cd.bendibao.com/wangdian/dian/5435749.shtm",
    "四川大学附属实验小学南区": "https://m.cd.bendibao.com/wangdian/dian/5435763.shtm",
    "四川大学附属实验小学明德学校": "https://m.cd.bendibao.com/wangdian/dian/5868267.shtm",
    "四川大学附属实验小学明雅学校": "https://m.cd.bendibao.com/wangdian/dian/5868304.shtm",
    "四川大学附属实验小学江安河分校": "https://cd.bendibao.com/wangdian/dian/93715.shtm",
    "四川大学附属实验小学清水河分校": "https://m.cd.bendibao.com/wangdian/dian/5435750.shtm",
    "四川大学附属实验小学西区": "https://m.cd.bendibao.com/wangdian/dian/5433885.shtm",
    "成都市望江楼小学": "https://m.cd.bendibao.com/wangdian/dian/5436422.shtm",
    "成都市玉林小学": "https://m.cd.bendibao.com/wangdian/dian/5432830.shtm",
    "成都市玉林小学果堰分校": "https://m.cd.bendibao.com/wangdian/dian/5868268.shtm",
    "成都市玉林中学": "https://m.cd.bendibao.com/wangdian/dian/5433548.shtm",
    "成都市西北中学": "https://m.cd.bendibao.com/wangdian/dian/5433090.shtm",
    "成都市第四十三中学校": "https://m.cd.bendibao.com/wangdian/dian/5433090.shtm",
    "成都市第十二中学（四川大学附属中学）": "https://m.cd.bendibao.com/wangdian/dian/5435782.shtm",
    "成都市第十二中学初中部": "https://m.cd.bendibao.com/wangdian/dian/5435782.shtm",
    "四川大学附属中学悦湖学校": "https://m.cd.bendibao.com/wangdian/dian/5433289.shtm",
    "四川大学附属中学新城分校": "https://m.cd.bendibao.com/wangdian/dian/5434795.shtm",
    "四川大学附属中学西区学校": "https://m.cd.bendibao.com/wangdian/32132.html",
    "北京第二外国语学院成都附属小学": "https://m.cd.bendibao.com/wangdian/dian/5435200.shtm",
    "北京第二外国语学院成都附属中学": "https://m.cd.bendibao.com/wangdian/dian/5435201.shtm",
    "成都石室双楠实验学校": "https://m.cd.bendibao.com/wangdian/dian/5433888.shtm",
    "成都石室佳兴外国语学校": "https://m.cd.bendibao.com/wangdian/dian/5433985.shtm",
    "成都西川中学": "https://m.cd.bendibao.com/wangdian/dian/5434796.shtm",
    "成都市武侯区西川实验学校": "https://m.cd.bendibao.com/wangdian/dian/5434796.shtm",
    "成都市龙祥路小学": "https://m.cd.bendibao.com/wangdian/dian/5433209.shtm",
    "成都市明远书院学校": "https://m.cd.bendibao.com/wangdian/dian/5436424.shtm",
    "成都市武侯实验中学": "https://m.cd.bendibao.com/wangdian/dian/5433112.shtm",
    "成都市通江实验学校": "https://m.cd.bendibao.com/wangdian/dian/5433983.shtm",
    "成都市群星美术学校": "https://m.cd.bendibao.com/wangdian/dian/5435228.shtm",
    "成都市武侯区丹勋实验学校": "https://m.cd.bendibao.com/wangdian/dian/5435227.shtm",
    "成都市科华中路小学": "https://m.cd.bendibao.com/wangdian/dian/93670.shtm",
    "成都市沙堰小学": "https://m.cd.bendibao.com/wangdian/dian/5435214.shtm",
    "成都市桐梓林小学": "https://m.cd.bendibao.com/edu/xiaoxuelist/wuhouqu/gongban/",
}


def load_mirror_map() -> dict[str, str]:
    merged = dict(BENDIBAO_BY_NAME)
    if SCRAPED.is_file():
        scraped = json.loads(SCRAPED.read_text(encoding="utf-8"))
        merged.update(scraped.get("mirrors") or {})
    return merged


def resolve_website(name: str, enrichment: dict) -> str | None:
    if name in enrichment.get("websites", {}):
        return enrichment["websites"][name]
    for group in enrichment.get("group_websites", []):
        if name.startswith(group["prefix"]):
            return group["website"]
    return None


def sync() -> dict:
    mirror_map = load_mirror_map()
    enrichment = yaml.safe_load(ENRICHMENT.read_text(encoding="utf-8")) or {}
    schools = yaml.safe_load(SCHOOLS.read_text(encoding="utf-8"))["schools"]
    alternate_urls: dict[str, list[dict]] = {}
    alternate_by_name: dict[str, list[dict]] = {}

    for school in schools:
        name = school["name"]
        mirror = mirror_map.get(name)
        if not mirror:
            continue
        row = {"url": mirror, "source": "bendibao"}
        by_bucket = alternate_by_name.setdefault(name, [])
        if not any(x["url"] == mirror for x in by_bucket):
            by_bucket.append(row)
        primary = (school.get("source_urls") or {}).get("website") or resolve_website(
            name, enrichment
        )
        if primary:
            bucket = alternate_urls.setdefault(primary, [])
            if not any(x["url"] == mirror for x in bucket):
                bucket.append(row)

    enrichment = yaml.safe_load(ENRICHMENT.read_text(encoding="utf-8")) or {}
    PRIMARY_MIRRORS = enrichment.get("primary_mirrors") or {}
    for primary, mirror in PRIMARY_MIRRORS.items():
        row = {"url": mirror, "source": "bendibao"}
        bucket = alternate_urls.setdefault(primary, [])
        if not any(x["url"] == mirror for x in bucket):
            bucket.append(row)

    enrichment["alternate_urls"] = alternate_urls
    enrichment["alternate_by_name"] = alternate_by_name
    ENRICHMENT.write_text(
        yaml.safe_dump(enrichment, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return {
        "primary_keys": len(alternate_urls),
        "by_name_keys": len(alternate_by_name),
        "mirror_entries": len(mirror_map),
        "scraped_file": SCRAPED.is_file(),
    }


def main() -> None:
    stats = sync()
    print(
        f"synced alternate_urls: {stats['primary_keys']} primaries, "
        f"{stats['by_name_keys']} by-name ({stats['mirror_entries']} mirrors in map)"
    )


if __name__ == "__main__":
    main()
