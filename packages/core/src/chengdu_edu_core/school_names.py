"""校名规范化与区内模糊匹配。"""
from __future__ import annotations

import re

_STRIP_PREFIXES = ("四川省", "四川", "成都市", "成都")
_SUFFIXES = ("学校", "小学", "中学", "实验学校", "外国语学校", "附属学校")


def normalize_school_name(name: str) -> str:
    text = re.sub(r"\s+", "", name.strip())
    for prefix in _STRIP_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break
    text = re.sub(r"[（(][^）)]*[）)]", "", text)
    return text


def _core_token(name: str) -> str:
    text = normalize_school_name(name)
    for suffix in _SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
            break
    return text


def match_school_name(
    candidate: str,
    known_names: list[str],
    *,
    aliases: dict[str, str] | None = None,
    min_core_len: int = 3,
) -> str | None:
    """在 known_names 中找与 candidate 最匹配的校名；无匹配返回 None。"""
    if not candidate or not known_names:
        return None

    cand = candidate.strip()
    if aliases:
        cand = aliases.get(cand, aliases.get(normalize_school_name(cand), cand))
    if cand in known_names:
        return cand

    cand_norm = normalize_school_name(cand)
    norm_map = {normalize_school_name(n): n for n in known_names}
    if cand_norm in norm_map:
        return norm_map[cand_norm]

    for known in known_names:
        kn = normalize_school_name(known)
        if cand_norm in kn or kn in cand_norm:
            if min(len(cand_norm), len(kn)) >= min_core_len:
                return known

    cand_core = _core_token(cand)
    if len(cand_core) < min_core_len:
        return None

    best: str | None = None
    best_len = 0
    for known in known_names:
        core = _core_token(known)
        if cand_core == core or cand_core in core or core in cand_core:
            overlap = min(len(cand_core), len(core))
            if overlap > best_len:
                best = known
                best_len = overlap
    return best
