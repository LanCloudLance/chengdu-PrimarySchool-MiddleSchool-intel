"""W3.4 武侯门户可读验收：搜索 API + 模板要素 + 可选 HTTP 探测。"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_ROOT = ROOT / "packages" / "api" / "src" / "chengdu_edu_api"
TEMPLATES = API_ROOT / "templates"


def check_scope_search_api() -> list[str]:
    errors: list[str] = []
    from chengdu_edu_api.routes import schools as schools_routes

    sig = inspect.signature(schools_routes.search_schools)
    if "scope_q" not in sig.parameters:
        errors.append("GET /api/schools missing scope_q parameter")
    from chengdu_edu_core.search_query import search_patterns

    if not search_patterns("玉林东路"):
        errors.append("search_patterns returned empty for street query")
    return errors


def check_templates() -> list[str]:
    errors: list[str] = []
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    if "yjrx" not in base and "招生入学服务平台" not in base:
        errors.append("base.html missing disclaimer / yjrx reference")
    index = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    if "scope_q" not in index:
        errors.append("index.html missing scope_q search field")
    detail = (TEMPLATES / "school_detail.html").read_text(encoding="utf-8")
    for token in ("mapping_badge", "mapping_provenance", "划片范围"):
        if token not in detail:
            errors.append(f"school_detail.html missing {token}")
    results = (TEMPLATES / "school_results.html").read_text(encoding="utf-8")
    if "mapping_status" not in results:
        errors.append("school_results.html missing mapping_status badge")
    return errors


def check_mapping_display() -> list[str]:
    errors: list[str] = []
    from chengdu_edu_api.mapping_display import DISCLAIMER_TEXT, MAPPING_STATUS_META

    if "仅供参考" not in DISCLAIMER_TEXT:
        errors.append("DISCLAIMER_TEXT incomplete")
    if "verified" not in MAPPING_STATUS_META or "reference" not in MAPPING_STATUS_META:
        errors.append("MAPPING_STATUS_META missing verified/reference")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Wuhou portal acceptance (W3.4)")
    parser.parse_args()

    sys.path.insert(0, str(ROOT / "packages" / "api" / "src"))
    sys.path.insert(0, str(ROOT / "packages" / "core" / "src"))

    errors: list[str] = []
    for checker in (check_scope_search_api, check_templates, check_mapping_display):
        errors.extend(checker())

    print("=== W3 portal checks ===")
    if errors:
        for err in errors:
            print("FAIL:", err)
        print("W3.4 acceptance: FAIL")
        return 1

    print("scope_q API: OK")
    print("templates (disclaimer, badge, provenance): OK")
    print("mapping_display: OK")
    print("W3.4 acceptance: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
