"""对指定区 image_list 情报源执行 PNG OCR 试点（不写入 DB，仅打印/导出 JSON）。"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

import httpx
import yaml

ROOT = Path(__file__).resolve().parent.parent
SOURCES = ROOT / "configs" / "district_mapping_sources.yaml"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
}


def fetch_html(client: httpx.Client, url: str) -> str | None:
    for candidate in (url, url.replace("://cd.", "://m.cd.")):
        try:
            resp = client.get(candidate, follow_redirects=True)
            if "拼图验证" in resp.text or len(resp.text) < 500:
                continue
            return resp.text
        except httpx.HTTPError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="OCR pilot for bendibao mapping PNG tables")
    parser.add_argument("--district", default="wuhou")
    parser.add_argument("--out", type=Path, help="optional JSON output path")
    args = parser.parse_args()

    from chengdu_edu_parsers.mapping_ocr import ocr_mapping_html

    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8"))
    urls = [
        e
        for e in cfg.get("districts", {}).get(args.district, {}).get("mapping_urls", [])
        if e.get("kind") == "image_list"
    ]
    if not urls:
        print(f"no image_list sources for {args.district}", file=sys.stderr)
        return 1

    with httpx.Client(timeout=60, headers=HEADERS) as client:
        for entry in urls:
            html = fetch_html(client, entry["url"])
            if html is None:
                print(f"fetch failed: {entry['url']}", file=sys.stderr)
                continue
            result = ocr_mapping_html(html, client=client)
            payload = {
                "district": args.district,
                "source_url": entry["url"],
                "image_urls": result.image_urls,
                "scopes": [asdict(s) for s in result.school_scopes],
                "ocr_line_count": len(result.ocr_lines),
                "errors": result.errors,
            }
            print(
                f"{args.district}: images={len(result.image_urls)} "
                f"scopes={len(result.school_scopes)} errors={len(result.errors)}"
            )
            if args.out:
                args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
