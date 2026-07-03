"""生成 2025 vs 2026 划片范围差异报告。

比较 configs/districts/{code}/mapping_scraped.json (2025) 与
mapping_scraped_2026.json (2026)，输出中文 Markdown 报告到
docs/2025-2026差异报告.md。

比较维度：
- 学校数量变化
- 新增学校（2026 有 2025 无）
- 消失学校（2025 有 2026 无）
- 范围变化学校（同名学校但 enrollment_scope 不同）
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parent.parent

CORE_DISTRICTS = (
    "jinjiang",
    "qingyang",
    "wuhou",
    "chenghua",
    "jinniu",
    "gaoxin",
    "tianfu",
)

DISTRICT_LABELS = {
    "jinjiang": "锦江区",
    "qingyang": "青羊区",
    "wuhou": "武侯区",
    "chenghua": "成华区",
    "jinniu": "金牛区",
    "gaoxin": "高新区",
    "tianfu": "天府新区",
}


@dataclass
class DistrictDiff:
    code: str
    label: str
    year_old: int
    year_new: int
    count_old: int
    count_new: int
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[tuple[str, str, str]] = field(default_factory=list)  # (name, old, new)
    unchanged: int = 0
    source_summary: dict[str, int] = field(default_factory=dict)


def _load_scopes(path: Path) -> dict:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    scopes = data.get("school_scopes") or []
    name_to_scope: dict[str, str] = {}
    for row in scopes:
        name = (row.get("school_name") or "").strip()
        if not name:
            continue
        scope = (row.get("enrollment_scope") or "").strip()
        # 同名学校取第一条（与导入脚本一致）
        if name not in name_to_scope:
            name_to_scope[name] = scope
    return name_to_scope


def _load_source_summary(path: Path) -> dict[str, int]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for row in data.get("school_scopes") or []:
        src = row.get("scope_source") or "unknown"
        out[src] = out.get(src, 0) + 1
    return out


def diff_district(code: str) -> DistrictDiff | None:
    base = ROOT / "configs" / "districts" / code
    old_path = base / "mapping_scraped.json"
    new_path = base / "mapping_scraped_2026.json"
    if not old_path.is_file() or not new_path.is_file():
        return None

    old_json = json.loads(old_path.read_text(encoding="utf-8"))
    new_json = json.loads(new_path.read_text(encoding="utf-8"))

    old_map = _load_scopes(old_path)
    new_map = _load_scopes(new_path)

    added = sorted(set(new_map) - set(old_map))
    removed = sorted(set(old_map) - set(new_map))
    common = set(old_map) & set(new_map)
    changed: list[tuple[str, str, str]] = []
    unchanged = 0
    for name in sorted(common):
        o = old_map[name]
        n = new_map[name]
        if _normalize(o) == _normalize(n):
            unchanged += 1
        else:
            changed.append((name, o, n))

    return DistrictDiff(
        code=code,
        label=DISTRICT_LABELS.get(code, code),
        year_old=int(old_json.get("data_year", 2025)),
        year_new=int(new_json.get("data_year", 2026)),
        count_old=len(old_map),
        count_new=len(new_map),
        added=added,
        removed=removed,
        changed=changed,
        unchanged=unchanged,
        source_summary=_load_source_summary(new_path),
    )


def _normalize(s: str) -> str:
    """规范化以便比较范围文本（仅去除首尾空白）。"""
    return s.strip()


def _short(scope: str, limit: int = 60) -> str:
    s = scope.replace("\n", " ").strip()
    if len(s) <= limit:
        return s
    return s[:limit] + "…"


def render_markdown(diffs: list[DistrictDiff]) -> str:
    lines: list[str] = []
    lines.append("# 成都七区 2025 vs 2026 划片范围差异报告")
    lines.append("")
    lines.append(
        f"> 本报告由 `scripts/diff_mapping_years.py` 自动生成。"
        f"比较 7 个核心区 2025 与 2026 学区划片数据。"
    )
    lines.append("")

    # 数据源分布
    lines.append("## 数据源分布（2026）")
    lines.append("")
    lines.append("| 区 | 条目数 | scope_source 分布 |")
    lines.append("|---|---:|---|")
    for d in diffs:
        src_desc = "、".join(
            f"`{k}`={v}" for k, v in sorted(d.source_summary.items())
        )
        lines.append(f"| {d.label}（{d.code}） | {d.count_new} | {src_desc} |")
    lines.append("")
    lines.append(
        "- `wechat_official`: 微信公众号文字版（结构化、可信度高）"
    )
    lines.append("- `ocr_image_needs_review`: 图片 OCR（需人工复核，质量偏低）")
    lines.append("- `bendibao_text`: 本地宝文字版（参考级）")
    lines.append("")

    # 汇总统计
    lines.append("## 汇总统计")
    lines.append("")
    lines.append("| 区 | 2025校数 | 2026校数 | 增减 | 新增 | 消失 | 变化 | 不变 |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    tot = {"old": 0, "new": 0, "add": 0, "rem": 0, "chg": 0}
    for d in diffs:
        delta = d.count_new - d.count_old
        sign = "+" if delta >= 0 else ""
        lines.append(
            f"| {d.label} | {d.count_old} | {d.count_new} | "
            f"{sign}{delta} | {len(d.added)} | {len(d.removed)} | "
            f"{len(d.changed)} | {d.unchanged} |"
        )
        tot["old"] += d.count_old
        tot["new"] += d.count_new
        tot["add"] += len(d.added)
        tot["rem"] += len(d.removed)
        tot["chg"] += len(d.changed)
    tot_delta = tot["new"] - tot["old"]
    sign = "+" if tot_delta >= 0 else ""
    lines.append(
        f"| **合计** | **{tot['old']}** | **{tot['new']}** | "
        f"**{sign}{tot_delta}** | **{tot['add']}** | **{tot['rem']}** | "
        f"**{tot['chg']}** | - |"
    )
    lines.append("")

    # 每区小节
    for d in diffs:
        lines.append(f"## {d.label}（{d.code}）")
        lines.append("")
        lines.append(
            f"学校数：{d.year_old}年 {d.count_old} → {d.year_new}年 "
            f"{d.count_new}（{d.count_new - d.count_old:+d}）"
        )
        lines.append("")

        if d.added:
            lines.append("### 新增学校（2026 有，2025 无）")
            lines.append("")
            lines.append("| 学校名称 |")
            lines.append("|---|")
            for n in d.added:
                lines.append(f"| {n} |")
            lines.append("")
        else:
            lines.append("### 新增学校：无")
            lines.append("")

        if d.removed:
            lines.append("### 消失学校（2025 有，2026 无）")
            lines.append("")
            lines.append("| 学校名称 |")
            lines.append("|---|")
            for n in d.removed:
                lines.append(f"| {n} |")
            lines.append("")
        else:
            lines.append("### 消失学校：无")
            lines.append("")

        if d.changed:
            lines.append("### 范围变化学校（同名但 enrollment_scope 不同）")
            lines.append("")
            lines.append("| 学校名称 | 旧范围摘要 | 新范围摘要 |")
            lines.append("|---|---|---|")
            for name, o, n in d.changed:
                lines.append(f"| {name} | {_short(o)} | {_short(n)} |")
            lines.append("")
        else:
            lines.append("### 范围变化学校：无")
            lines.append("")

    lines.append("## OCR 数据质量提示")
    lines.append("")
    ocr_districts = [
        d for d in diffs if d.source_summary.get("ocr_image_needs_review", 0) > 0
    ]
    if ocr_districts:
        lines.append(
            "以下区的 2026 数据来自图片 OCR，标为 `ocr_image_needs_review`，"
            "导入时应设 mapping_status=`pending_review`，需人工复核："
        )
        lines.append("")
        for d in ocr_districts:
            n_ocr = d.source_summary.get("ocr_image_needs_review", 0)
            lines.append(f"- **{d.label}**（{d.code}）：{n_ocr} 条 OCR 条目")
        lines.append("")
    else:
        lines.append("无 OCR 数据。")
        lines.append("")

    lines.append("## 结论与建议")
    lines.append("")
    lines.append("1. 来自微信公众号文字版的区（锦江、青羊、成华、天府）数据结构化程度高，可直接导入。")
    lines.append("2. 来自 OCR 图片的区（武侯、金牛、高新）需人工复核后再对外展示。")
    lines.append("3. 高新区另有 10 条 `bendibao_text` 参考数据，可作参考级情报。")
    lines.append("4. 天府新区 2026 校数降幅较大（38→17），建议核查是否为 OCR 漏识别或数据源不全。")
    lines.append("5. 武侯区校数由 47 降至 30，同样建议复核 OCR 质量。")
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> int:
    diffs: list[DistrictDiff] = []
    for code in CORE_DISTRICTS:
        d = diff_district(code)
        if d is None:
            print(f"skip {code}: missing files")
            continue
        diffs.append(d)
        print(
            f"{code}: old={d.count_old} new={d.count_new} "
            f"add={len(d.added)} rem={len(d.removed)} chg={len(d.changed)}"
        )

    md = render_markdown(diffs)
    out_path = ROOT / "docs" / "2025-2026差异报告.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(f"report written: {out_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
