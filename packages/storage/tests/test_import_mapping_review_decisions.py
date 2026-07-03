import csv
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from chengdu_edu_core.enums import (
    DistrictLevel,
    PolicyType,
    RecordType,
    SchoolLevel,
    SchoolType,
)
from chengdu_edu_storage.orm import (
    District,
    EnrollmentPolicy,
    FieldChange,
    RecordVersion,
    School,
)

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.import_mapping_review_decisions import import_review_decisions  # noqa: E402


async def _seed_mapping_policy(db_session):
    district_id = uuid.uuid4()
    school_id = uuid.uuid4()
    policy_id = uuid.uuid4()
    db_session.add(
        District(
            id=district_id,
            name="金牛区",
            code="jinniu",
            level=DistrictLevel.CORE,
        )
    )
    db_session.add(
        School(
            id=school_id,
            name="成都市五丁小学校",
            district_id=district_id,
            type=SchoolType.PUBLIC,
            level=SchoolLevel.PRIMARY,
        )
    )
    db_session.add(
        EnrollmentPolicy(
            id=policy_id,
            district_id=district_id,
            school_id=school_id,
            policy_type=PolicyType.DISTRICT_MAPPING,
            year=2026,
            fields={
                "enrollment_scope": "泊木一至三街",
                "mapping_status": "pending_review",
            },
            current_version=1,
        )
    )
    await db_session.commit()
    return school_id, policy_id


def _write_review_csv(path: Path, *, school_id, status, decision, notes=""):
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "district_code",
                "district_name",
                "school_id",
                "school_name",
                "year",
                "mapping_status",
                "enrollment_scope",
                "source_page",
                "reference_year",
                "framework_year",
                "notes",
                "review_decision",
                "review_notes",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "district_code": "jinniu",
                "district_name": "金牛区",
                "school_id": str(school_id),
                "school_name": "成都市五丁小学校",
                "year": "2026",
                "mapping_status": status,
                "enrollment_scope": "泊木一至三街",
                "notes": "",
                "review_decision": decision,
                "review_notes": notes,
            }
        )


@pytest.mark.asyncio
async def test_import_review_decisions_dry_run_does_not_update(
    db_session, tmp_path
):
    school_id, policy_id = await _seed_mapping_policy(db_session)
    csv_path = tmp_path / "review.csv"
    _write_review_csv(
        csv_path,
        school_id=school_id,
        status="pending_review",
        decision="verified",
    )

    result = await import_review_decisions(db_session, csv_path, dry_run=True)

    policy = await db_session.get(EnrollmentPolicy, policy_id)
    assert result.updated == 1
    assert policy.fields["mapping_status"] == "pending_review"
    assert policy.current_version == 1


@pytest.mark.asyncio
async def test_import_review_decisions_updates_status_and_audit_rows(
    db_session, tmp_path
):
    school_id, policy_id = await _seed_mapping_policy(db_session)
    csv_path = tmp_path / "review.csv"
    _write_review_csv(
        csv_path,
        school_id=school_id,
        status="pending_review",
        decision="verified",
        notes="已按教育局 PDF 核对",
    )

    result = await import_review_decisions(
        db_session,
        csv_path,
        reviewed_by="codex",
    )

    policy = await db_session.get(EnrollmentPolicy, policy_id)
    assert result.updated == 1
    assert policy.fields["mapping_status"] == "verified"
    assert policy.fields["previous_mapping_status"] == "pending_review"
    assert policy.fields["review_notes"] == "已按教育局 PDF 核对"
    assert policy.fields["reviewed_by"] == "codex"
    assert policy.current_version == 2

    versions = (
        await db_session.execute(
            select(RecordVersion).where(
                RecordVersion.record_type == RecordType.ENROLLMENT,
                RecordVersion.record_id == policy_id,
            )
        )
    ).scalars().all()
    assert len(versions) == 1
    changes = (
        await db_session.execute(
            select(FieldChange).where(
                FieldChange.record_type == RecordType.ENROLLMENT,
                FieldChange.record_id == policy_id,
            )
        )
    ).scalars().all()
    changed_paths = {change.field_path for change in changes}
    assert "fields.mapping_status" in changed_paths
    assert "fields.review_notes" in changed_paths


@pytest.mark.asyncio
async def test_import_review_decisions_skips_stale_csv(db_session, tmp_path):
    school_id, policy_id = await _seed_mapping_policy(db_session)
    csv_path = tmp_path / "review.csv"
    _write_review_csv(
        csv_path,
        school_id=school_id,
        status="pending_official",
        decision="verified",
    )

    result = await import_review_decisions(db_session, csv_path)

    policy = await db_session.get(EnrollmentPolicy, policy_id)
    assert result.updated == 0
    assert result.skipped_stale == 1
    assert policy.fields["mapping_status"] == "pending_review"
    assert policy.current_version == 1
