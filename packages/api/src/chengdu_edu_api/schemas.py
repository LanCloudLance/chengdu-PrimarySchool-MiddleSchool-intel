from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from chengdu_edu_core.enums import (
    DistrictLevel,
    JobStatus,
    ParserStrategy,
    PolicyType,
    SchoolLevel,
    SchoolType,
    SourceType,
)


class SourceMeta(BaseModel):
    url: str | None = None


class DistrictOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    level: DistrictLevel


class SchoolSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    short_name: str | None = None
    district_id: UUID
    district_code: str
    type: SchoolType
    level: SchoolLevel
    address: str | None = None


class PaginatedSchools(BaseModel):
    items: list[SchoolSummary]
    total: int
    offset: int
    limit: int


class PolicySourceInfo(BaseModel):
    url: str | None = None
    fetched_at: datetime | None = None
    confidence: float | None = None
    has_recent_changes: bool = False


class EnrollmentPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID | None
    district_id: UUID
    policy_type: PolicyType
    year: int
    fields: dict
    current_version: int
    source: SourceMeta
    fetched_at: datetime | None = None
    confidence: float | None = None
    has_recent_changes: bool = False


class PromotionPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_id: UUID
    target_school_id: UUID | None
    district_id: UUID
    year: int
    fields: dict
    current_version: int
    source: SourceMeta
    fetched_at: datetime | None = None
    confidence: float | None = None
    has_recent_changes: bool = False


class SchoolDetailOut(BaseModel):
    id: UUID
    name: str
    short_name: str | None = None
    district_id: UUID
    district_code: str
    type: SchoolType
    level: SchoolLevel
    address: str | None = None
    source_urls: dict = Field(default_factory=dict)
    metadata: dict = Field(default_factory=dict)
    enrollment_policies: list[EnrollmentPolicyOut] = Field(default_factory=list)
    promotion_policies: list[PromotionPolicyOut] = Field(default_factory=list)


class FieldChangeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    record_type: str
    record_id: UUID
    from_version: int
    to_version: int
    field_path: str
    old_value: str | None
    new_value: str | None
    detected_at: datetime


class SchoolHistoryOut(BaseModel):
    school_id: UUID
    changes: list[FieldChangeOut]


class PaginatedEnrollmentPolicies(BaseModel):
    items: list[EnrollmentPolicyOut]
    total: int
    offset: int
    limit: int


class PaginatedPromotionPolicies(BaseModel):
    items: list[PromotionPolicyOut]
    total: int
    offset: int
    limit: int


class JobTriggerRequest(BaseModel):
    scope: str
    target_id: UUID | None = None


class JobTriggerResponse(BaseModel):
    status: str
    scope: str
    target_id: UUID | None = None


class JobRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    status: JobStatus
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    docs_fetched: int
    changes_detected: int


class PaginatedJobRuns(BaseModel):
    items: list[JobRunOut]
    total: int
    offset: int
    limit: int


class DataSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    source_type: SourceType
    url: str
    parser_strategy: ParserStrategy
    schedule: str
    district_id: UUID | None
    school_id: UUID | None
    is_active: bool


class DataSourcePatch(BaseModel):
    is_active: bool


class StatsOut(BaseModel):
    districts: int
    schools: int
    sources: int
    active_sources: int
    enrollment_policies: int
    promotion_policies: int
    job_runs: int
