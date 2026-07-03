from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DistrictConfig:
    name: str
    code: str
    level: str


@dataclass(frozen=True)
class SourceConfig:
    name: str
    source_type: str
    url: str
    parser_strategy: str
    schedule: str
    district_code: str
    rule_file: str | None = None
    is_active: bool = True


@dataclass(frozen=True)
class ScheduleConfig:
    defaults: dict[str, str]
    season_override: dict


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_districts(config_dir: Path | str) -> list[DistrictConfig]:
    data = _load_yaml(Path(config_dir) / "districts.yaml")
    return [DistrictConfig(**entry) for entry in data["districts"]]


def load_sources(config_dir: Path | str) -> list[SourceConfig]:
    data = _load_yaml(Path(config_dir) / "sources.yaml")
    return [SourceConfig(**entry) for entry in data["sources"]]


def load_schedules(config_dir: Path | str) -> ScheduleConfig:
    data = _load_yaml(Path(config_dir) / "schedules.yaml")
    return ScheduleConfig(
        defaults=data["defaults"],
        season_override=data.get("season_override", {}),
    )
