"""划片一览表 PNG OCR 试点（本地宝 data-echo / cdbdb/edu 长图）。"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from io import BytesIO

from chengdu_edu_parsers.mapping_parser import SchoolScope, _clean_scope, _normalize_table_school_name

_MAPPING_IMG_PATTERNS = (
    re.compile(r'data-echo="([^"]+)"', re.I),
    re.compile(r'bigpicsrc="([^"]+)"', re.I),
    re.compile(r'https?://imgbdb[^"\'\s<>]+cdbdb/edu/[^"\'\s<>]+\.(?:png|jpg|jpeg)', re.I),
)

_NAME_FRAGMENT_END = re.compile(r"(?:小学|学校|实验学校|分校)$")


@dataclass
class OcrMappingResult:
    image_urls: list[str] = field(default_factory=list)
    ocr_lines: list[str] = field(default_factory=list)
    school_scopes: list[SchoolScope] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def extract_mapping_image_urls(html: str) -> list[str]:
    """从本地宝文章 HTML 提取划片一览表长图 URL（过滤广告缩略图）。"""
    found: list[str] = []
    seen: set[str] = set()
    for pattern in _MAPPING_IMG_PATTERNS:
        for match in pattern.finditer(html):
            url = match.group(1) if match.lastindex else match.group(0)
            url = url.strip()
            if not url.startswith("http"):
                continue
            if "/sl/" in url or "dazheimg" in url or len(url) < 40:
                continue
            if "cdbdb/edu" not in url and "whbdb" not in url:
                continue
            if url in seen:
                continue
            seen.add(url)
            found.append(url)
    return found


def _load_rapid_ocr():
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as exc:
        raise RuntimeError(
            "rapidocr-onnxruntime 未安装；请执行: uv pip install rapidocr-onnxruntime pillow"
        ) from exc
    return RapidOCR()


def ocr_image_bytes(image_bytes: bytes, *, min_confidence: float = 0.5) -> list[tuple[list, str, float]]:
    ocr = _load_rapid_ocr()
    result, _ = ocr(image_bytes)
    if not result:
        return []
    return [(box, text.strip(), conf) for box, text, conf in result if text.strip() and conf >= min_confidence]


def _column_side(xc: float, image_width: int) -> str:
    ratio = xc / image_width
    if ratio < 0.10:
        return "zone"
    if ratio < 0.36:
        return "name"
    return "scope"


def _is_name_fragment(text: str) -> bool:
    text = re.sub(r"\s+", "", text)
    if len(text) < 2:
        return True
    return _NAME_FRAGMENT_END.search(text) is None


def _normalize_ocr_school_name(raw: str) -> str | None:
    name = re.sub(r"\s+", "", raw)
    name = re.sub(r"^\d+", "", name)
    name = name.replace("武候", "武侯")
    if any(token in name for token in ("片号", "服务范围", "一览表", "划片范围", "小学名称")):
        return None
    if not _NAME_FRAGMENT_END.search(name):
        return None
    parts = [name] if name.startswith(("成都", "四川", "北京")) else [name]
    normalized = _normalize_table_school_name(parts)
    if normalized:
        return normalized
    if not name.startswith(("成都", "四川", "北京")):
        name = f"成都市{name}"
    return name if len(name) >= 6 else None


def parse_ocr_table_boxes(
    boxes: list[tuple[list, str, float]],
    *,
    image_width: int,
    row_bucket_px: int = 28,
    header_skip_y: float = 150,
) -> list[SchoolScope]:
    """按 OCR 边框分列（片号 | 校名 | 范围）并合并跨行单元格。"""
    row_cells: dict[int, dict[str, str]] = defaultdict(lambda: {"zone": "", "name": "", "scope": ""})
    for box, text, _conf in boxes:
        x0, y0 = box[0]
        x1, y1 = box[2]
        xc = (x0 + x1) / 2
        yc = (y0 + y1) / 2
        if yc < header_skip_y:
            continue
        bucket = int(round(yc / row_bucket_px))
        side = _column_side(xc, image_width)
        row_cells[bucket][side] += text

    records: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    name_carry = ""

    for bucket in sorted(row_cells):
        row = row_cells[bucket]
        combined_name = f"{name_carry}{row['name']}{row['zone']}".strip()
        zone_match = re.match(r"^(\d+)", combined_name)
        zone = zone_match.group(1) if zone_match else ""
        name_body = re.sub(r"^\d+", "", combined_name)
        scope_part = row["scope"].strip()

        if name_body and not _is_name_fragment(name_body):
            candidate = _normalize_ocr_school_name(name_body)
            if candidate:
                if current:
                    records.append(current)
                current = {
                    "school_name": candidate,
                    "enrollment_scope": scope_part,
                    "zone": zone,
                }
                name_carry = ""
                continue

        if name_body and _is_name_fragment(name_body):
            name_carry += name_body
            if scope_part and current is not None:
                current["enrollment_scope"] += scope_part
            continue

        if scope_part and current is not None:
            current["enrollment_scope"] += scope_part

    if current:
        records.append(current)

    scopes: list[SchoolScope] = []
    seen: set[str] = set()
    for row in records:
        name = row["school_name"]
        scope = _clean_scope(row["enrollment_scope"])
        if name in seen or len(scope) < 12:
            continue
        if not re.search(r"[路街道巷村苑区号界至]", scope):
            continue
        seen.add(name)
        zone = row.get("zone") or ""
        scopes.append(
            SchoolScope(
                school_name=name,
                enrollment_scope=scope,
                source_excerpt=f"OCR片号{zone} {name}" if zone else f"OCR {name}",
            )
        )
    return scopes


def ocr_mapping_image(image_bytes: bytes) -> OcrMappingResult:
    """对单张划片长图执行 OCR 并解析为 school_scopes。"""
    from PIL import Image

    image = Image.open(BytesIO(image_bytes))
    width = image.size[0]
    boxes = ocr_image_bytes(image_bytes)
    lines = [text for _box, text, _conf in boxes]
    scopes = parse_ocr_table_boxes(boxes, image_width=width) if boxes else []
    return OcrMappingResult(ocr_lines=lines, school_scopes=scopes)


def _is_wuhou_mapping_header(lines: list[str]) -> bool:
    header = "".join(lines[:20])
    return "武侯" in header and ("划片" in header or "一览表" in header)


def ocr_mapping_html(html: str, *, client=None) -> OcrMappingResult:
    """从文章 HTML 提取划片图 URL，下载并 OCR（需 httpx.Client 或自动创建）。"""
    import httpx

    urls = extract_mapping_image_urls(html)
    result = OcrMappingResult(image_urls=urls)
    if not urls:
        result.errors.append("no_mapping_images")
        return result

    owns_client = client is None
    if owns_client:
        client = httpx.Client(
            timeout=60,
            headers={"User-Agent": "Mozilla/5.0 (compatible; chengdu-edu-intel/0.1)"},
            follow_redirects=True,
        )
    try:
        merged: list[SchoolScope] = []
        seen_names: set[str] = set()
        for url in urls:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                if len(resp.content) < 200_000:
                    continue
                partial = ocr_mapping_image(resp.content)
                if partial.ocr_lines and not _is_wuhou_mapping_header(partial.ocr_lines):
                    continue
                result.ocr_lines.extend(partial.ocr_lines)
                for scope in partial.school_scopes:
                    if scope.school_name in seen_names:
                        continue
                    seen_names.add(scope.school_name)
                    merged.append(scope)
            except Exception as exc:
                result.errors.append(f"{url}: {exc}")
        result.school_scopes = merged
    finally:
        if owns_client:
            client.close()
    return result
