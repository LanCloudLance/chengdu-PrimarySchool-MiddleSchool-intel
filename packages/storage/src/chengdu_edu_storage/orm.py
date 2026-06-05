import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from chengdu_edu_core.enums import (
    DistrictLevel,
    JobStatus,
    ParserStrategy,
    PolicyType,
    RecordType,
    SchoolLevel,
    SchoolType,
    SourceType,
)

JsonType = JSON().with_variant(JSONB(), "postgresql")
UuidType = Uuid(as_uuid=True)


def _enum_column(enum_cls, name: str):
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda members: [member.value for member in members],
    )


class Base(DeclarativeBase):
    pass


class District(Base):
    __tablename__ = "districts"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(50), unique=True)
    level: Mapped[DistrictLevel] = mapped_column(_enum_column(DistrictLevel, "district_level"))


class School(Base):
    __tablename__ = "schools"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    short_name: Mapped[str | None] = mapped_column(String(100))
    district_id: Mapped[uuid.UUID] = mapped_column(UuidType, ForeignKey("districts.id"))
    type: Mapped[SchoolType] = mapped_column(_enum_column(SchoolType, "school_type"))
    level: Mapped[SchoolLevel] = mapped_column(_enum_column(SchoolLevel, "school_level"))
    address: Mapped[str | None] = mapped_column(Text)
    source_urls: Mapped[dict] = mapped_column(JsonType, default=dict)
    metadata_: Mapped[dict] = mapped_column("metadata", JsonType, default=dict)


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[SourceType] = mapped_column(_enum_column(SourceType, "source_type"))
    url: Mapped[str] = mapped_column(Text)
    parser_strategy: Mapped[ParserStrategy] = mapped_column(
        _enum_column(ParserStrategy, "parser_strategy")
    )
    schedule: Mapped[str] = mapped_column(String(100))
    district_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType, ForeignKey("districts.id")
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(UuidType, ForeignKey("schools.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class RawDocument(Base):
    __tablename__ = "raw_documents"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UuidType, ForeignKey("data_sources.id"))
    content_hash: Mapped[str] = mapped_column(String(64))
    raw_content: Mapped[str | None] = mapped_column(Text)
    raw_file_path: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    http_status: Mapped[int | None] = mapped_column(Integer)


class EnrollmentPolicy(Base):
    __tablename__ = "enrollment_policies"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID | None] = mapped_column(UuidType, ForeignKey("schools.id"))
    district_id: Mapped[uuid.UUID] = mapped_column(UuidType, ForeignKey("districts.id"))
    policy_type: Mapped[PolicyType] = mapped_column(_enum_column(PolicyType, "policy_type"))
    year: Mapped[int] = mapped_column(Integer)
    fields: Mapped[dict] = mapped_column(JsonType, default=dict)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType, ForeignKey("raw_documents.id")
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    current_version: Mapped[int] = mapped_column(Integer, default=1)


class PromotionPolicy(Base):
    __tablename__ = "promotion_policies"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    school_id: Mapped[uuid.UUID] = mapped_column(UuidType, ForeignKey("schools.id"))
    target_school_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType, ForeignKey("schools.id")
    )
    district_id: Mapped[uuid.UUID] = mapped_column(UuidType, ForeignKey("districts.id"))
    year: Mapped[int] = mapped_column(Integer)
    fields: Mapped[dict] = mapped_column(JsonType, default=dict)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType, ForeignKey("raw_documents.id")
    )
    current_version: Mapped[int] = mapped_column(Integer, default=1)


class RecordVersion(Base):
    __tablename__ = "record_versions"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    record_type: Mapped[RecordType] = mapped_column(_enum_column(RecordType, "record_type"))
    record_id: Mapped[uuid.UUID] = mapped_column(UuidType)
    version: Mapped[int] = mapped_column(Integer)
    fields_snapshot: Mapped[dict] = mapped_column(JsonType, default=dict)
    source_doc_id: Mapped[uuid.UUID | None] = mapped_column(
        UuidType, ForeignKey("raw_documents.id")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class FieldChange(Base):
    __tablename__ = "field_changes"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    record_type: Mapped[RecordType] = mapped_column(_enum_column(RecordType, "record_type"))
    record_id: Mapped[uuid.UUID] = mapped_column(UuidType)
    from_version: Mapped[int] = mapped_column(Integer)
    to_version: Mapped[int] = mapped_column(Integer)
    field_path: Mapped[str] = mapped_column(Text)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobRun(Base):
    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(UuidType, primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UuidType, ForeignKey("data_sources.id"))
    status: Mapped[JobStatus] = mapped_column(_enum_column(JobStatus, "job_status"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)
    docs_fetched: Mapped[int] = mapped_column(Integer, default=0)
    changes_detected: Mapped[int] = mapped_column(Integer, default=0)
