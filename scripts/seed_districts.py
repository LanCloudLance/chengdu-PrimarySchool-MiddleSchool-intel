import asyncio
from pathlib import Path

import yaml
from sqlalchemy import select

from chengdu_edu_core.enums import DistrictLevel
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import District

ROOT = Path(__file__).resolve().parent.parent
DISTRICTS_CONFIG = ROOT / "configs" / "districts.yaml"


def load_districts_config() -> list[dict]:
    data = yaml.safe_load(DISTRICTS_CONFIG.read_text(encoding="utf-8"))
    return data["districts"]


async def seed_districts() -> int:
    districts = load_districts_config()
    inserted = 0

    async with SessionLocal() as session:
        for entry in districts:
            result = await session.execute(
                select(District).where(District.code == entry["code"])
            )
            existing = result.scalar_one_or_none()
            level = DistrictLevel(entry["level"])
            if existing is None:
                session.add(
                    District(
                        name=entry["name"],
                        code=entry["code"],
                        level=level,
                    )
                )
                inserted += 1
            else:
                existing.name = entry["name"]
                existing.level = level
        await session.commit()

    return inserted


async def main() -> None:
    inserted = await seed_districts()
    total = len(load_districts_config())
    print(f"seeded districts: {total} configured, {inserted} newly inserted")


if __name__ == "__main__":
    asyncio.run(main())
