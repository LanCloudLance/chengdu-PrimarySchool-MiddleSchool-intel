import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.verify_district_parity import db_check, format_db_status  # noqa: E402


def _db(**overrides):
    base = {
        "schools": 43,
        "file_schools": 43,
        "file_scopes": 46,
        "mapping_total": 41,
        "mapping_mapped": 35,
        "verified": 0,
        "reference": 5,
        "pending_review": 30,
        "pending_official": 6,
        "unknown_status": 0,
        "enrollment": 43,
        "intel_mapping": 1,
        "intel_mirror": 0,
        "gov_policy": 1,
    }
    base.update(overrides)
    return base


def test_2026_db_check_accepts_pending_review_status():
    ok, issues = db_check("gaoxin", _db(), year=2026)

    assert ok, issues


def test_2026_db_check_allows_tianfu_reform_pending_official():
    ok, issues = db_check(
        "tianfu",
        _db(
            schools=41,
            file_schools=41,
            file_scopes=12,
            mapping_total=38,
            mapping_mapped=0,
            verified=0,
            reference=0,
            pending_review=0,
            pending_official=38,
            enrollment=41,
        ),
        year=2026,
    )

    assert ok, issues


def test_2026_db_check_rejects_unknown_status_counts():
    ok, issues = db_check(
        "jinjiang",
        _db(unknown_status=1, mapping_total=42, verified=24, pending_official=3),
        year=2026,
    )

    assert not ok
    assert any("unknown_mapping_status" in issue for issue in issues)


def test_2025_db_check_keeps_strict_mapped_ratio():
    ok, issues = db_check("gaoxin", _db(), year=2025)

    assert not ok
    assert any("db_mapping_mapped" in issue for issue in issues)


def test_format_db_status_includes_2026_status_breakdown():
    text = format_db_status(_db(), year=2026)

    assert "status(v=0 ref=5 review=30 pending=6 unknown=0)" in text
