"""intel_entries table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intel_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("school_id", sa.Uuid(), nullable=True),
        sa.Column(
            "intel_type",
            sa.Enum(
                "mapping",
                "enrollment",
                "promotion",
                "gov_article",
                "mirror_page",
                name="intel_type",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_title", sa.String(length=300), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("structured_fields", sa.JSON(), nullable=False),
        sa.Column("data_year", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_reference", sa.Boolean(), nullable=False, server_default="false"),
        sa.ForeignKeyConstraint(["district_id"], ["districts.id"]),
        sa.ForeignKeyConstraint(["school_id"], ["schools.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intel_entries_district_type_year",
        "intel_entries",
        ["district_id", "intel_type", "data_year"],
    )
    op.create_index(
        "ix_intel_entries_content_hash",
        "intel_entries",
        ["content_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_intel_entries_content_hash", table_name="intel_entries")
    op.drop_index("ix_intel_entries_district_type_year", table_name="intel_entries")
    op.drop_table("intel_entries")
