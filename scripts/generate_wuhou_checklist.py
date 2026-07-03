"""生成武侯区学校补全 checklist（Markdown）。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WUHOU_YAML = ROOT / "configs" / "districts" / "wuhou" / "schools.yaml"
ENRICHMENT_YAML = ROOT / "configs" / "districts" / "wuhou" / "enrichment.yaml"
CHECKLIST_MD = ROOT / "configs" / "districts" / "wuhou" / "CHECKLIST.md"

TYPE_LABEL = {"public": "公办", "private": "民办"}
LEVEL_LABEL = {"primary": "小学", "middle": "初中"}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def enrichment_kind(school: dict, enrichment: dict) -> str:
    name = school["name"]
    urls = school.get("source_urls") or {}
    if school.get("inventory_status") == "verified":
        return "verified"
    if urls.get("website"):
        if urls.get("group_note"):
            return "group_website"
        if enrichment.get("no_website", {}).get(name):
            return "no_website"
        return "website"
    if enrichment.get("no_website", {}).get(name):
        return "no_website"
    return "pending"


def detail_line(school: dict, kind: str) -> str:
    urls = school.get("source_urls") or {}
    if kind == "verified":
        via = urls.get("verification_via", "primary")
        resolved = urls.get("verification_url") or urls.get("website", "")
        if via == "mirror_only":
            reason = school.get("enrichment_note") or "无独立官网"
            channel = urls.get("contact_channel")
            line = f"{reason}；镜像已验证 `{resolved}`"
            if channel:
                line += f"；联系渠道：{channel}"
            return line
        if via == "alternate":
            return f"镜像已验证 `{resolved}`（主站 `{urls.get('website', '')}`）"
        return f"官网已验证 `{resolved}`"
    if kind == "website":
        return f"官网 `{urls.get('website', '')}`"
    if kind == "group_website":
        note = urls.get("group_note") or "集团官网"
        return f"集团 `{urls.get('website', '')}`（{note}）"
    if kind == "no_website":
        reason = school.get("enrichment_note") or "无独立官网"
        channel = urls.get("contact_channel")
        if channel:
            return f"{reason}；联系渠道：{channel}"
        return reason
    return "待补全"


def checkbox(kind: str) -> str:
    return "- [x]" if kind != "pending" else "- [ ]"


def generate_checklist() -> str:
    doc = load_yaml(WUHOU_YAML)
    enrichment = load_yaml(ENRICHMENT_YAML)
    schools = doc["schools"]
    today = date.today().isoformat()

    done: list[tuple[dict, str]] = []
    pending: list[dict] = []
    verified: list[dict] = []

    for school in schools:
        kind = enrichment_kind(school, enrichment)
        if kind == "pending":
            pending.append(school)
        else:
            done.append((school, kind))
            if kind == "verified":
                verified.append(school)

    lines = [
        "# 武侯区学校补全 Checklist",
        "",
        f"> 生成日期：{today} | 共 {len(schools)} 校 | "
        f"已补全 {len(done)} | 未补全 {len(pending)} | "
        f"官网已验证 {len(verified)}",
        "",
        "## 汇总",
        "",
        "| 状态 | 数量 |",
        "|------|------|",
        f"| 已补全（含无独立官网） | {len(done)} |",
        f"| 未补全 | {len(pending)} |",
        f"| 路径已验证 | {len(verified)} |",
        "",
        "## 已补全",
        "",
    ]

    by_level: dict[str, list[tuple[dict, str]]] = {"primary": [], "middle": []}
    for school, kind in done:
        by_level[school["level"]].append((school, kind))

    for level in ("primary", "middle"):
        lines.append(f"### {LEVEL_LABEL[level]}（{len(by_level[level])}）")
        lines.append("")
        for school, kind in sorted(by_level[level], key=lambda x: x[0]["name"]):
            tag = TYPE_LABEL[school["type"]]
            status_tag = {
                "verified": "verified",
                "website": "enriched",
                "group_website": "enriched+集团",
                "no_website": "enriched+无站",
            }[kind]
            lines.append(
                f"{checkbox(kind)} **{school['name']}** "
                f"（{tag}{LEVEL_LABEL[level]} · {status_tag}）"
            )
            lines.append(f"  - {detail_line(school, kind)}")
        lines.append("")

    lines.extend(["## 未补全", ""])
    if not pending:
        lines.append("_全部学校已完成补全调研。_")
    else:
        for level in ("primary", "middle"):
            level_pending = [s for s in pending if s["level"] == level]
            if not level_pending:
                continue
            lines.append(f"### {LEVEL_LABEL[level]}（{len(level_pending)}）")
            lines.append("")
            for school in sorted(level_pending, key=lambda s: s["name"]):
                tag = TYPE_LABEL[school["type"]]
                lines.append(
                    f"- [ ] **{school['name']}** （{tag}{LEVEL_LABEL[level]}）"
                )
            lines.append("")

    lines.extend(
        [
            "## 维护命令",
            "",
            "```bash",
            "~/.local/bin/uv run python scripts/sync_wuhou_alternate_urls.py",
            "~/.local/bin/uv run python scripts/build_wuhou_inventory.py",
            "~/.local/bin/uv run python scripts/verify_wuhou_schools.py",
            "~/.local/bin/uv run python scripts/generate_wuhou_checklist.py",
            "docker compose exec api uv run python scripts/import_schools.py",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    content = generate_checklist()
    CHECKLIST_MD.write_text(content, encoding="utf-8")
    doc = load_yaml(WUHOU_YAML)
    pending = sum(
        1 for s in doc["schools"] if s.get("inventory_status") == "listed"
    )
    print(f"wrote {CHECKLIST_MD} (listed remaining: {pending})")


if __name__ == "__main__":
    main()
