"""门户学校模糊搜索条件构建。"""
from __future__ import annotations

import re

from sqlalchemy import ColumnElement, or_

from chengdu_edu_core.school_names import normalize_school_name


def _search_patterns(q: str) -> list[str]:
    text = q.strip()
    if not text:
        return []

    patterns: list[str] = []
    seen: set[str] = set()

    def add(value: str) -> None:
        value = value.strip()
        if len(value) < 2 or value in seen:
            return
        seen.add(value)
        patterns.append(value)

    add(text)
    add(normalize_school_name(text))

    for token in re.split(r"[\s,，、/]+", text):
        add(token)
        add(normalize_school_name(token))

    # 常见简称：去掉行政区前缀后再搜
    for prefix in ("武侯区", "锦江区", "青羊区", "成华区", "金牛区", "高新区", "天府新区"):
        if text.startswith(prefix):
            add(text[len(prefix) :])

    return patterns


def school_fuzzy_filter(q: str | None, *columns: ColumnElement) -> ColumnElement | None:
    """对 name / short_name / address 等列做 OR 模糊匹配。"""
    if not q or not q.strip():
        return None

    patterns = _search_patterns(q)
    if not patterns:
        return None

    conditions: list[ColumnElement] = []
    for pattern in patterns:
        like = f"%{pattern}%"
        for column in columns:
            conditions.append(column.ilike(like))

    return or_(*conditions)
