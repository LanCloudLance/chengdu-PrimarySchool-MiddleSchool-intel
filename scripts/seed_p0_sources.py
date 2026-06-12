import asyncio
from pathlib import Path

import yaml
from sqlalchemy import select

from chengdu_edu_core.enums import ParserStrategy, SourceType
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import DataSource, District

ROOT = Path(__file__).resolve().parent.parent
SOURCES_CONFIG = ROOT / "configs" / "sources.yaml"


def load_sources_config() -> list[dict]:
    data = yaml.safe_load(SOURCES_CONFIG.read_text(encoding="utf-8"))
    return data["sources"]


async def seed_p0_sources() -> int:
    sources = load_sources_config()
    inserted = 0

    async with SessionLocal() as session:
        districts_result = await session.execute(select(District))
        districts = {district.code: district.id for district in districts_result.scalars()}
        if not districts:
            raise RuntimeError(
                "districts must be seeded first (run: uv run python scripts/seed_districts.py)"
            )

        for entry in sources:
            district_code = entry["district_code"]
            if district_code not in districts:
                raise KeyError(
                    f"district_code {district_code!r} not found; seed districts first"
                )

            existing_result = await session.execute(
                select(DataSource).where(DataSource.name == entry["name"])
            )
            if existing_result.scalar_one_or_none() is not None:
                continue

            metadata: dict = {}
            if rule_file := entry.get("rule_file"):
                metadata["rule_file"] = rule_file
            for key in ("data_year", "registration_url", "fallback_url", "notes"):
                if key in entry:
                    metadata[key] = entry[key]

            session.add(
                DataSource(
                    name=entry["name"],
                    source_type=SourceType(entry["source_type"]),
                    url=entry["url"],
                    parser_strategy=ParserStrategy(entry["parser_strategy"]),
                    schedule=entry["schedule"],
                    district_id=districts[district_code],
                    is_active=entry.get("is_active", True),
                    metadata_=metadata,
                )
            )
            inserted += 1

        await session.commit()

    return inserted


async def main() -> None:
    inserted = await seed_p0_sources()
    total = len(load_sources_config())
    print(f"seeded P0 sources: {total} configured, {inserted} newly inserted")


if __name__ == "__main__":
    asyncio.run(main())
