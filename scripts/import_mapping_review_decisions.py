"""Import manual mapping review decisions from exported CSV."""

from __future__ import annotations

import argparse
import asyncio
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_core.diff import compute_field_changes
from chengdu_edu_core.enums import PolicyType, RecordType
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import (
    District,
    EnrollmentPolicy,
    FieldChange,
    RecordVersion,
)

VALID_REVIEW_DECISIONS = {
    "verified",
    "reference",
    "pending_review",
    "pending_official",
}

REQUIRED_COLUMNS = {
    "district_code",
    "school_id",
    "year",
    "mapping_status",
    "review_decision",
}


@dataclass
class ReviewImportResult:
    updated: int = 0
    skipped_blank: int = 0
    skipped_unchanged: int = 0
    skipped_stale: int = 0
    missing_policy: int = 0
    invalid_rows: int = 0

    @property
    def ok(self) -> bool:
        return self.missing_policy == 0 and self.invalid_rows == 0


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _load_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            missing_cols = ", ".join(sorted(missing))
            raise ValueError(f"missing required CSV columns: {missing_cols}")
        return [dict(row) for row in reader]


async def _find_policy(
    session: AsyncSession,
    *,
    district_code: str,
    school_id: UUID,
    year: int,
) -> EnrollmentPolicy | None:
    stmt = (
        select(EnrollmentPolicy)
        .join(District, EnrollmentPolicy.district_id == District.id)
        .where(
            District.code == district_code,
            EnrollmentPolicy.school_id == school_id,
            EnrollmentPolicy.year == year,
            EnrollmentPolicy.policy_type == PolicyType.DISTRICT_MAPPING,
        )
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def _reviewed_fields(
    old_fields: dict,
    *,
    review_decision: str,
    review_notes: str,
    reviewed_by: str,
    reviewed_at: datetime,
) -> dict:
    fields = dict(old_fields)
    old_status = _clean(fields.get("mapping_status"))
    fields["mapping_status"] = review_decision
    fields["reviewed_by"] = reviewed_by
    fields["reviewed_at"] = reviewed_at.isoformat()
    fields["review_source"] = "mapping_review_csv"
    if old_status != review_decision:
        fields["previous_mapping_status"] = old_status
    if review_notes:
        fields["review_notes"] = review_notes
    return fields


def _add_audit_rows(
    session: AsyncSession,
    *,
    policy: EnrollmentPolicy,
    old_fields: dict,
    new_fields: dict,
    new_version: int,
) -> None:
    session.add(
        RecordVersion(
            record_type=RecordType.ENROLLMENT,
            record_id=policy.id,
            version=new_version,
            fields_snapshot=new_fields,
            source_doc_id=policy.source_doc_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    for change in compute_field_changes(old_fields, new_fields):
        session.add(
            FieldChange(
                record_type=RecordType.ENROLLMENT,
                record_id=policy.id,
                from_version=new_version - 1,
                to_version=new_version,
                field_path=change.field_path,
                old_value=change.old_value or None,
                new_value=change.new_value or None,
                detected_at=datetime.now(timezone.utc),
            )
        )


async def import_review_decisions(
    session: AsyncSession,
    csv_path: Path,
    *,
    reviewed_by: str = "manual_review",
    dry_run: bool = False,
) -> ReviewImportResult:
    result = ReviewImportResult()
    reviewed_at = datetime.now(timezone.utc)

    for row in _load_rows(csv_path):
        review_decision = _clean(row.get("review_decision"))
        if not review_decision:
            result.skipped_blank += 1
            continue
        if review_decision not in VALID_REVIEW_DECISIONS:
            result.invalid_rows += 1
            continue

        try:
            school_id = UUID(_clean(row.get("school_id")))
            year = int(_clean(row.get("year")))
        except (TypeError, ValueError):
            result.invalid_rows += 1
            continue

        policy = await _find_policy(
            session,
            district_code=_clean(row.get("district_code")),
            school_id=school_id,
            year=year,
        )
        if policy is None:
            result.missing_policy += 1
            continue

        old_fields = dict(policy.fields or {})
        current_status = _clean(old_fields.get("mapping_status"))
        csv_status = _clean(row.get("mapping_status"))
        if csv_status and csv_status != current_status:
            result.skipped_stale += 1
            continue

        new_fields = _reviewed_fields(
            old_fields,
            review_decision=review_decision,
            review_notes=_clean(row.get("review_notes")),
            reviewed_by=reviewed_by,
            reviewed_at=reviewed_at,
        )
        if new_fields == old_fields:
            result.skipped_unchanged += 1
            continue

        if not dry_run:
            new_version = policy.current_version + 1
            policy.fields = new_fields
            policy.current_version = new_version
            _add_audit_rows(
                session,
                policy=policy,
                old_fields=old_fields,
                new_fields=new_fields,
                new_version=new_version,
            )
        result.updated += 1

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    return result


async def _main_async(args: argparse.Namespace) -> int:
    async with SessionLocal() as session:
        result = await import_review_decisions(
            session,
            Path(args.csv_path),
            reviewed_by=args.reviewed_by,
            dry_run=args.dry_run,
        )

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(
        f"{mode}: updated={result.updated} "
        f"blank={result.skipped_blank} unchanged={result.skipped_unchanged} "
        f"stale={result.skipped_stale} missing={result.missing_policy} "
        f"invalid={result.invalid_rows}"
    )
    return 0 if result.ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import manual mapping review decisions from CSV export."
    )
    parser.add_argument("csv_path")
    parser.add_argument("--reviewed-by", default="manual_review")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
