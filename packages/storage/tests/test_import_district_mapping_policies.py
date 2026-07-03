import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts import import_district_mapping_policies as importer  # noqa: E402


def test_load_scraped_2026_requires_2026_file(monkeypatch, tmp_path):
    district_dir = tmp_path / "configs" / "districts" / "gaoxin"
    district_dir.mkdir(parents=True)
    (district_dir / "mapping_scraped.json").write_text(
        json.dumps({"data_year": 2025, "school_scopes": []}),
        encoding="utf-8",
    )
    monkeypatch.setattr(importer, "ROOT", tmp_path)

    with pytest.raises(FileNotFoundError):
        importer.load_scraped("gaoxin", year_filter=2026)


def test_load_scraped_2026_reads_2026_file(monkeypatch, tmp_path):
    district_dir = tmp_path / "configs" / "districts" / "gaoxin"
    district_dir.mkdir(parents=True)
    (district_dir / "mapping_scraped.json").write_text(
        json.dumps({"data_year": 2025, "school_scopes": []}),
        encoding="utf-8",
    )
    (district_dir / "mapping_scraped_2026.json").write_text(
        json.dumps({"data_year": 2026, "school_scopes": [{"school_name": "A"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(importer, "ROOT", tmp_path)

    doc = importer.load_scraped("gaoxin", year_filter=2026)

    assert doc["data_year"] == 2026
    assert doc["school_scopes"][0]["school_name"] == "A"
