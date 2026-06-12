"""小升初升学对应区域 PNG OCR（本地宝 片号 | 小学 | 初中代码 | 初中名称 | 备注）。"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field

from chengdu_edu_parsers.mapping_ocr import ocr_image_bytes
from chengdu_edu_parsers.mapping_parser import PromotionLink, _normalize_table_school_name

_PRIMARY_END = re.compile(r"(?:小学|附小|实验学校|分校|学校)$")
_MIDDLE_END = re.compile(r"(?:中学|实验学校|学校|初中部)$")
_CODE = re.compile(r"^\d{5}$")


@dataclass
class OcrPromotionResult:
    image_urls: list[str] = field(default_factory=list)
    ocr_lines: list[str] = field(default_factory=list)
    promotion_links: list[PromotionLink] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _column_kind(xc: float, image_width: int) -> str:
    ratio = xc / image_width
    if ratio < 0.18:
        return "code"
    if ratio < 0.48:
        return "primary"
    if ratio < 0.62:
        return "mid_code"
    if ratio < 0.84:
        return "middle"
    return "notes"


def _normalize_primary_name(raw: str) -> str | None:
    name = re.sub(r"\s+", "", raw)
    if not name or len(name) < 5:
        return None
    if any(token in name for token in ("片号", "升学对应", "初中学校", "备注", "一览表")):
        return None
    if not _PRIMARY_END.search(name):
        return None
    parts = [name] if name.startswith(("成都", "四川", "北京")) else [name]
    normalized = _normalize_table_school_name(parts)
    if normalized:
        return normalized
    if not name.startswith(("成都", "四川", "北京")):
        name = f"成都市{name}"
    return name if len(name) >= 6 else None


def _normalize_middle_name(raw: str) -> str | None:
    name = re.sub(r"\s+", "", raw)
    name = name.replace("武候", "武侯")
    name = re.sub(r"[（(][^）)]*[）)]$", "", name)
    if not name or len(name) < 5:
        return None
    if any(token in name for token in ("片号", "升学对应", "初中学校", "备注", "名称")):
        return None
    if not _MIDDLE_END.search(name):
        return None
    if name.startswith("四川省成都市"):
        name = "成都市" + name[len("四川省成都市") :]
    if not name.startswith(("成都", "四川", "北京")):
        name = f"成都市{name}"
    return name


def parse_promotion_ocr_boxes(
    boxes: list[tuple[list, str, float]],
    *,
    image_width: int,
    row_bucket_px: int = 22,
    header_skip_y: float = 45,
) -> list[PromotionLink]:
    """按 OCR 边框分列，按片号分组产出小学→初中对口。"""
    row_cells: dict[int, dict[str, list[str]]] = defaultdict(
        lambda: {"code": [], "primary": [], "mid_code": [], "middle": [], "notes": []}
    )
    for box, text, _conf in boxes:
        x0, y0 = box[0]
        x1, y1 = box[2]
        xc = (x0 + x1) / 2
        yc = (y0 + y1) / 2
        if yc < header_skip_y:
            continue
        bucket = int(round(yc / row_bucket_px))
        kind = _column_kind(xc, image_width)
        row_cells[bucket][kind].append(text.strip())

    zones: list[dict] = []
    current: dict | None = None

    def flush_zone() -> None:
        nonlocal current
        if current and (current["primaries"] or current["middles"]):
            zones.append(current)
        current = None

    for bucket in sorted(row_cells):
        row = row_cells[bucket]
        code_text = "".join(row["code"] + row["mid_code"])
        notes_text = "".join(row["notes"])

        zone_match = re.search(r"(\d+)", code_text)
        if zone_match and row["code"] and not row["primary"]:
            flush_zone()
            current = {
                "zone": zone_match.group(1),
                "primaries": [],
                "middles": [],
                "notes": "",
                "lottery": False,
            }

        if current is None:
            current = {"zone": "", "primaries": [], "middles": [], "notes": "", "lottery": False}

        for fragment in row["primary"]:
            primary = _normalize_primary_name(fragment)
            if primary and primary not in current["primaries"]:
                current["primaries"].append(primary)

        for fragment in row["middle"]:
            middle = _normalize_middle_name(fragment)
            if middle and middle not in current["middles"]:
                current["middles"].append(middle)

        if "多校划片" in notes_text or "电脑随机" in notes_text:
            current["lottery"] = True
        if notes_text:
            current["notes"] = notes_text

    flush_zone()

    links: list[PromotionLink] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for zone in zones:
        if not zone["primaries"] or not zone["middles"]:
            continue
        promo_type = "多校划片摇号" if zone["lottery"] or len(zone["middles"]) > 1 else "对口直升"
        excerpt = f"片号{zone['zone']} " if zone["zone"] else ""
        if zone["notes"]:
            excerpt += zone["notes"]
        else:
            excerpt += promo_type
        targets = zone["middles"]
        for primary in zone["primaries"]:
            key = (primary, tuple(targets))
            if key in seen:
                continue
            seen.add(key)
            links.append(
                PromotionLink(
                    primary_name=primary,
                    target_names=list(targets),
                    promotion_type=promo_type,
                    source_excerpt=excerpt[:200],
                )
            )
    return links


def ocr_promotion_image(image_bytes: bytes) -> OcrPromotionResult:
    from PIL import Image

    image = Image.open(__import__("io").BytesIO(image_bytes))
    width = image.size[0]
    boxes = ocr_image_bytes(image_bytes)
    lines = [text for _box, text, _conf in boxes]
    links = parse_promotion_ocr_boxes(boxes, image_width=width) if boxes else []
    return OcrPromotionResult(ocr_lines=lines, promotion_links=links)


def _is_promotion_header(lines: list[str]) -> bool:
    header = "".join(lines[:20])
    if "划片一览表" in header and "升学对应" not in header:
        return False
    return "升学对应区域" in header or (
        "片号" in header and ("初中学校" in header or "初中学校名称" in header)
    )


def _is_promotion_table_page(lines: list[str]) -> bool:
    """续页长图可能无表头，但有片号+校名列。"""
    body = "".join(lines)
    if "划片一览表" in body and "升学对应" not in body:
        return False
    has_primary = "小学" in body
    has_middle = "中学" in body or "实验学校" in body
    has_code = bool(re.search(r"\d{5}", body))
    return has_primary and has_middle and has_code


def ocr_promotion_html(html: str, *, client=None) -> OcrPromotionResult:
    """从本地宝文章 HTML 提取升学划片 PNG 并 OCR。"""
    import httpx

    from chengdu_edu_parsers.mapping_parser import extract_bendibao_content_images

    urls = extract_bendibao_content_images(html)
    result = OcrPromotionResult(image_urls=urls)
    if not urls:
        result.errors.append("no_promotion_images")
        return result

    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=60,
            headers={"User-Agent": "Mozilla/5.0 (compatible; chengdu-edu-intel/0.1)"},
            follow_redirects=True,
            verify=False,
        )
    try:
        merged: list[PromotionLink] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for url in urls:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                if len(resp.content) < 8_000:
                    continue
                partial = ocr_promotion_image(resp.content)
                if partial.ocr_lines and not (
                    _is_promotion_header(partial.ocr_lines)
                    or _is_promotion_table_page(partial.ocr_lines)
                ):
                    continue
                result.ocr_lines.extend(partial.ocr_lines)
                for link in partial.promotion_links:
                    key = (link.primary_name, tuple(link.target_names))
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(link)
            except Exception as exc:
                result.errors.append(f"{url}: {exc}")
        result.promotion_links = merged
    finally:
        if owns_client:
            client.close()
    return result
