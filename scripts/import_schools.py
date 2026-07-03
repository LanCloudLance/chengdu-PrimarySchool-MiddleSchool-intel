import asyncio
from pathlib import Path

import yaml

from chengdu_edu_core.enums import SchoolLevel, SchoolType
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.school_repository import SchoolRepository

ROOT = Path(__file__).resolve().parent.parent
SCHOOLS_CONFIG = ROOT / "configs" / "schools.yaml"
DISTRICT_SCHOOLS_GLOB = "configs/districts/*/schools.yaml"


def load_schools_config(path: Path | str | None = None) -> list[dict]:
    config_path = Path(path) if path else SCHOOLS_CONFIG
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data.get("schools") or []


def load_all_school_configs() -> list[dict]:
    schools = load_schools_config(SCHOOLS_CONFIG)
    for path in sorted(ROOT.glob(DISTRICT_SCHOOLS_GLOB)):
        schools.extend(load_schools_config(path))
    return schools


async def import_schools_from_yaml(
    path: str | Path, repo: SchoolRepository
) -> int:
    schools = load_schools_config(path)
    districts = await repo.get_district_code_map()
    count = 0

    for row in schools:
        district_id = districts[row["district_code"]]
        metadata: dict = {}
        for key in (
            "notes",
            "data_year",
            "verified",
            "verification_source",
            "verified_at",
            "role",
            "inventory_status",
            "list_category",
            "phone",
            "enrichment_note",
            "enrichment_resolved_at",
        ):
            if key in row and row[key] is not None:
                metadata[key] = row[key]

        await repo.upsert_school(
            name=row["name"],
            district_id=district_id,
            type=SchoolType(row["type"]),
            level=SchoolLevel(row["level"]),
            short_name=row.get("short_name"),
            address=row.get("address"),
            source_urls=row.get("source_urls", {}),
            metadata=metadata or None,
            former_names=row.get("former_names"),
        )
        count += 1

    return count


async def main() -> None:
    async with SessionLocal() as session:
        repo = SchoolRepository(session)
        schools = load_all_school_configs()
        districts = await repo.get_district_code_map()
        canonical: dict[str, set[str]] = {}
        count = 0
        for row in schools:
            code = row["district_code"]
            canonical.setdefault(code, set()).add(row["name"])
            district_id = districts[code]
            metadata: dict = {}
            for key in (
                "notes",
                "data_year",
                "verified",
                "verification_source",
                "verified_at",
                "role",
                "inventory_status",
                "list_category",
                "phone",
                "enrichment_note",
                "enrichment_resolved_at",
            ):
                if key in row and row[key] is not None:
                    metadata[key] = row[key]
            await repo.upsert_school(
                name=row["name"],
                district_id=district_id,
                type=SchoolType(row["type"]),
                level=SchoolLevel(row["level"]),
                short_name=row.get("short_name"),
                address=row.get("address"),
                source_urls=row.get("source_urls", {}),
                metadata=metadata or None,
                former_names=row.get("former_names"),
            )
            count += 1

        pruned = 0
        for code, names in canonical.items():
            removed = await repo.prune_orphan_schools(
                district_id=districts[code], keep_names=names
            )
            pruned += removed
            if removed:
                print(f"pruned {removed} orphan schools in {code}")

    print(f"imported schools: {count} (pruned orphans: {pruned})")


if __name__ == "__main__":
    asyncio.run(main())
