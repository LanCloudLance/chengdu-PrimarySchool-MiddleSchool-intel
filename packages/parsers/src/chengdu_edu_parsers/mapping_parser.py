"""划片范围与对口初中文本解析。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

_SCHOOL_SUFFIX = r"(?:小学|中学|学校|实验学校|外国语学校|附属(?:实验)?(?:小学|中学|学校))"
_PROMO_PAIR = re.compile(
    rf"([\u4e00-\u9fffA-Za-z0-9·（）()\-]+{_SCHOOL_SUFFIX})"
    rf"(?:[^。\n]{{0,30}})?(?:对口|直升|对应|划片至|升入)"
    rf"[^。\n]{{0,30}}"
    rf"([\u4e00-\u9fffA-Za-z0-9·（）()\-]+{_SCHOOL_SUFFIX})"
)
_SCHOOL_NAME = rf"([\u4e00-\u9fffA-Za-z0-9·\-]+(?:{_SCHOOL_SUFFIX})(?:[（(][^）)]*[）)])?)"
_NUMBERED_SCOPE = re.compile(
    rf"\d+\.\s*\n?\s*{_SCHOOL_NAME}\s*\n"
    rf"([^。\n][^\n]{{7,400}}?)(?=\n\s*\d+\.\s|\n[一二三四]、|\s*\Z)",
    re.MULTILINE | re.DOTALL,
)
_INLINE_SCOPE = re.compile(
    rf"{_SCHOOL_NAME}[：:]\s*([^。\n]{{8,400}})"
)
_ZONE_BLOCK = re.compile(
    r"([一二三四五六七八九十\d]+[、.]?\s*[^。\n]{0,20}(?:片区|学区)[^。\n]{0,30})\n"
    r"(范围四至[：:]\s*[^。\n]{10,400})",
    re.MULTILINE,
)
_GROUP_MIDDLE = re.compile(
    rf"([\u4e00-\u9fff]{{2,8}})(?:小学|附小|实验小学)[^。\n]{{0,20}}"
    rf"(?:对口|直升|对应)[^。\n]{{0,20}}"
    rf"([\u4e00-\u9fff]{{2,8}})(?:中学|附中|实验中学)",
)


@dataclass
class SchoolScope:
    school_name: str
    enrollment_scope: str
    source_excerpt: str = ""


@dataclass
class PromotionLink:
    primary_name: str
    target_names: list[str] = field(default_factory=list)
    promotion_type: str = "对口直升"
    source_excerpt: str = ""


@dataclass
class MappingParseResult:
    school_scopes: list[SchoolScope] = field(default_factory=list)
    zone_blocks: list[dict[str, str]] = field(default_factory=list)
    promotion_links: list[PromotionLink] = field(default_factory=list)


def extract_article_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for selector in (".content", ".article", "#content", ".art_content", "article"):
        node = soup.select_one(selector)
        if node:
            return node.get_text("\n", strip=True)
    return soup.get_text("\n", strip=True)


def _clean_scope(text: str) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    return text[:800]


def parse_school_scopes(text: str) -> list[SchoolScope]:
    scopes: list[SchoolScope] = []
    seen: set[str] = set()

    for match in _NUMBERED_SCOPE.finditer(text):
        name = match.group(1).strip()
        scope = _clean_scope(match.group(2))
        if len(scope) < 8 or name in seen:
            continue
        if re.match(r"^\d+\.", scope):
            continue
        if not re.search(r"[至界路街道巷大道区以南以北以东以西]", scope):
            continue
        seen.add(name)
        scopes.append(
            SchoolScope(
                school_name=name,
                enrollment_scope=scope,
                source_excerpt=f"{name}\n{scope[:120]}",
            )
        )

    for match in _INLINE_SCOPE.finditer(text):
        name = match.group(1).strip()
        scope = _clean_scope(match.group(2))
        if len(scope) < 8 or name in seen:
            continue
        if any(k in scope for k in ("温馨提示", "微信搜索", "分享本文")):
            continue
        seen.add(name)
        scopes.append(
            SchoolScope(
                school_name=name,
                enrollment_scope=scope,
                source_excerpt=f"{name}：{scope[:120]}",
            )
        )

    return scopes


def parse_zone_blocks(text: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    for match in _ZONE_BLOCK.finditer(text):
        blocks.append(
            {
                "zone_label": match.group(1).strip(),
                "zone_boundary": match.group(2).strip(),
            }
        )
    return blocks


def parse_promotion_links(text: str) -> list[PromotionLink]:
    links: list[PromotionLink] = []
    seen: set[tuple[str, str]] = set()

    for match in _PROMO_PAIR.finditer(text):
        primary = match.group(1).strip()
        target = match.group(2).strip()
        key = (primary, target)
        if key in seen:
            continue
        seen.add(key)
        promo_type = "摇号" if "摇号" in match.group(0) else "对口直升"
        links.append(
            PromotionLink(
                primary_name=primary,
                target_names=[target],
                promotion_type=promo_type,
                source_excerpt=match.group(0)[:200],
            )
        )

    for match in _GROUP_MIDDLE.finditer(text):
        primary = f"{match.group(1)}小学"
        target = f"{match.group(2)}中学"
        key = (primary, target)
        if key in seen:
            continue
        seen.add(key)
        links.append(
            PromotionLink(
                primary_name=primary,
                target_names=[target],
                promotion_type="对口直升",
                source_excerpt=match.group(0)[:200],
            )
        )

    return links


def infer_group_promotion_links(
    primary_names: list[str],
    middle_names: list[str],
    *,
    min_token_len: int = 2,
) -> list[PromotionLink]:
    """根据共享品牌词推断小学→初中对口（如 棕北、玉林）。"""
    links: list[PromotionLink] = []
    seen: set[tuple[str, str]] = set()
    stop_tokens = {
        "实验",
        "外国语",
        "附属",
        "学校",
        "小学",
        "中学",
        "第一",
        "第二",
        "第三",
        "校区",
        "分校",
        "武侯",
        "锦江",
        "青羊",
        "成华",
        "金牛",
        "高新",
        "天府",
    }

    def token(name: str) -> str | None:
        cleaned = re.sub(r"(四川省|四川|成都市|成都)", "", name)
        for suffix in (
            "附属实验小学",
            "附属小学",
            "实验学校",
            "实验小学",
            "外国语学校",
            "小学",
            "中学",
        ):
            if cleaned.endswith(suffix):
                cleaned = cleaned[: -len(suffix)]
                break
        cleaned = cleaned.strip()
        if len(cleaned) < min_token_len or cleaned in stop_tokens:
            return None
        return cleaned

    middle_tokens = {token(n): n for n in middle_names if token(n)}

    for primary in primary_names:
        tok = token(primary)
        if not tok:
            continue
        for mtok, middle in middle_tokens.items():
            if not mtok or mtok in stop_tokens:
                continue
            if tok == mtok:
                key = (primary, middle)
                if key in seen:
                    continue
                seen.add(key)
                links.append(
                    PromotionLink(
                        primary_name=primary,
                        target_names=[middle],
                        promotion_type="对口直升",
                        source_excerpt=f"品牌词推断：{tok}",
                    )
                )
    return links


def _normalize_table_school_name(parts: list[str]) -> str | None:
    name = "".join(parts).strip()
    if not name or len(name) < 4:
        return None
    if not name.endswith(("小学", "学校", "实验学校", "分校")):
        return None
    if not name.startswith(("成都", "四川", "北京")):
        name = f"成都市{name}"
    return name


_ADJUSTMENT_SECTION = re.compile(
    r"[一二三四五六七八九十]+、\s*"
    r"((?:成都市)?[^。\n]{2,48}?(?:小学|学校)(?:[（(][^）)]*[）)])?)"
    r"(?:拟确定的|调整后的)?入学划片范围[^\n]*\n+"
    r"([^(\n][^\n]{10,800}?)"
    r"(?=\n[一二三四五六七八九十]+、|\n温馨提示|\Z)",
    re.MULTILINE | re.DOTALL,
)


def _normalize_adjustment_school_name(raw: str) -> str:
    name = re.sub(r"\s+", "", raw.strip())
    name = re.sub(r"[（(]小学[）)]", "", name)
    name = name.replace("川大附小", "四川大学附属实验小学")
    if name.startswith("川大附"):
        name = "四川大学附属" + name[3:]
    if not name.startswith(("成都", "四川", "北京")):
        name = f"成都市{name}"
    return name


def parse_mapping_adjustment_sections(text: str) -> list[SchoolScope]:
    """解析教育局「划片范围调整/确定公告」版式（一、XX学校…范围\\n段落）。"""
    scopes: list[SchoolScope] = []
    seen: set[str] = set()
    for match in _ADJUSTMENT_SECTION.finditer(text):
        raw_title = match.group(1).strip()
        if "其他事项" in raw_title:
            continue
        name = _normalize_adjustment_school_name(raw_title)
        scope = _clean_scope(match.group(2))
        scope = re.sub(r"^该校划片范围为[：:]?\s*", "", scope)
        if len(scope) < 8 or name in seen:
            continue
        if not re.search(r"[至界路街道巷大道区以南以北以东以西]", scope):
            continue
        seen.add(name)
        scopes.append(
            SchoolScope(
                school_name=name,
                enrollment_scope=scope,
                source_excerpt=f"{name}\n{scope[:120]}",
            )
        )
    return scopes


def extract_bendibao_content_images(html: str) -> list[str]:
    """提取本地宝正文中的划片示意图（PNG 一览表）。"""
    from chengdu_edu_parsers.mapping_ocr import extract_mapping_image_urls

    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".content") or soup.select_one(".article") or soup
    urls: list[str] = []
    seen: set[str] = set()
    for img in content.select("img"):
        for attr in ("src", "data-src", "data-original", "data-echo", "bigpicsrc"):
            src = img.get(attr)
            if not src or not src.startswith("http"):
                continue
            if any(token in src for token in ("header-logo", "app-logo", "/icons/", "/sl/")):
                continue
            if "bdb" not in src and "bendibao" not in src:
                continue
            if src in seen:
                continue
            seen.add(src)
            urls.append(src)
    for url in extract_mapping_image_urls(html):
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def parse_bendibao_mapping_tables(html: str) -> list[SchoolScope]:
    """解析本地宝「划片一览表」HTML 表格（武侯区等常见版式）。"""
    soup = BeautifulSoup(html, "html.parser")
    scopes: list[SchoolScope] = []
    seen: set[str] = set()

    for table in soup.select("table"):
        for tr in table.select("tr"):
            cells = [td.get_text(strip=True) for td in tr.select("td")]
            if len(cells) < 3:
                continue
            scope = cells[-1]
            if len(scope) < 12:
                continue
            if scope in ("服务范围", "小学名称", "片号"):
                continue
            if cells[0] in ("片号", "小学名称"):
                continue

            start = 1 if cells[0].isdigit() else 0
            name = _normalize_table_school_name(cells[start:-1])
            if not name or name in seen:
                continue
            if not re.search(r"[路街道巷村苑区号界至]", scope):
                continue

            seen.add(name)
            zone_no = cells[0] if cells[0].isdigit() else ""
            scopes.append(
                SchoolScope(
                    school_name=name,
                    enrollment_scope=_clean_scope(scope),
                    source_excerpt=f"片号{zone_no} {name}" if zone_no else name,
                )
            )
    return scopes


def _merge_school_scopes(*groups: list[SchoolScope]) -> list[SchoolScope]:
    best: dict[str, SchoolScope] = {}
    for group in groups:
        for scope in group:
            prev = best.get(scope.school_name)
            if prev is None or len(scope.enrollment_scope) > len(prev.enrollment_scope):
                best[scope.school_name] = scope
    return list(best.values())


def parse_mapping_document(html: str, *, kind: str = "school_scope") -> MappingParseResult:
    text = extract_article_text(html)
    table_scopes = parse_bendibao_mapping_tables(html) if kind != "image_list" else []
    text_scopes = parse_school_scopes(text)
    if kind == "adjustment":
        text_scopes = parse_mapping_adjustment_sections(text)
    elif kind == "school_scope":
        text_scopes = _merge_school_scopes(
            text_scopes, parse_mapping_adjustment_sections(text)
        )
    return MappingParseResult(
        school_scopes=_merge_school_scopes(table_scopes, text_scopes),
        zone_blocks=parse_zone_blocks(text),
        promotion_links=parse_promotion_links(text),
    )


_SCOPE_SOURCE_RANK = {
    "override": 0,
    "adjustment": 1,
    "html": 2,
    "ocr": 3,
}


def merge_scope_dicts(rows: list[dict]) -> list[dict]:
    """合并多源划片：override > 公告 > HTML 表 > OCR；同层再比 verified 与年份。"""
    best: dict[str, dict] = {}

    def rank(row: dict) -> tuple:
        source = _SCOPE_SOURCE_RANK.get(row.get("scope_source") or "html", 2)
        ref = 1 if row.get("is_reference") else 0
        year = int(row.get("intel_year") or row.get("data_year") or 0)
        scope_len = len(row.get("enrollment_scope") or "")
        return (source, ref, -year, -scope_len)

    for row in rows:
        key = row.get("school_name") or ""
        if not key:
            continue
        prev = best.get(key)
        if prev is None or rank(row) < rank(prev):
            best[key] = row
    return list(best.values())
