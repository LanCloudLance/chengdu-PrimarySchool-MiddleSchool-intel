"""从 configs/sources.yaml 同步更新已存在数据源的 URL 与 rule_file（按 name 匹配）。"""
import asyncio
from pathlib import Path

import yaml
from sqlalchemy import select

from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import DataSource

ROOT = Path(__file__).resolve().parent.parent
SOURCES_CONFIG = ROOT / "configs" / "sources.yaml"


async def sync_sources() -> int:
    entries = yaml.safe_load(SOURCES_CONFIG.read_text(encoding="utf-8"))["sources"]
    updated = 0
    async with SessionLocal() as session:
        for entry in entries:
            result = await session.execute(
                select(DataSource).where(DataSource.name == entry["name"])
            )
            row = result.scalar_one_or_none()
            if row is None:
                continue
            row.url = entry["url"]
            row.is_active = entry.get("is_active", True)
            meta = dict(row.metadata_ or {})
            if rf := entry.get("rule_file"):
                meta["rule_file"] = rf
            row.metadata_ = meta
            updated += 1
        await session.commit()
    return updated


async def main() -> None:
    n = await sync_sources()
    print(f"synced {n} data source URLs from configs/sources.yaml")


if __name__ == "__main__":
    asyncio.run(main())
