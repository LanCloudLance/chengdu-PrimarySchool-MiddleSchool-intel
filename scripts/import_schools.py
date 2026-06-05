import asyncio
from pathlib import Path

import yaml

from chengdu_edu_core.enums import SchoolLevel, SchoolType
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.school_repository import SchoolRepository

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS_CONFIG = ROOT / "configs" / "schools.yaml"


def load_schools_config(path: Path | str | None = None) -> list[dict]:
    config_path = Path(path) if path else SCHOOLS_CONFIG
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data["schools"]


async def import_schools_from_yaml(
    path: str | Path, repo: SchoolRepository
) -> int:
    schools = load_schools_config(path)
    districts = await repo.get_district_code_map()
    count = 0

    for row in schools:
        district_id = districts[row["district_code"]]
        metadata: dict = {}
        if notes := row.get("notes"):
            metadata["notes"] = notes

        await repo.upsert_school(
            name=row["name"],
            district_id=district_id,
            type=SchoolType(row["type"]),
            level=SchoolLevel(row["level"]),
            short_name=row.get("short_name"),
            address=row.get("address"),
            source_urls=row.get("source_urls", {}),
            metadata=metadata or None,
        )
        count += 1

    return count


async def main() -> None:
    async with SessionLocal() as session:
        repo = SchoolRepository(session)
        count = await import_schools_from_yaml(SCHOOLS_CONFIG, repo)
    print(f"imported schools: {count}")


if __name__ == "__main__":
    asyncio.run(main())
