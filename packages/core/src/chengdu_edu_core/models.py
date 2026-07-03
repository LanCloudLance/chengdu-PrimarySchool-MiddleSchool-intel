from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from chengdu_edu_core.enums import ParserStrategy, PolicyType, RecordType


class RawDocument(BaseModel):
    source_id: UUID
    content_hash: str
    raw_content: str
    raw_file_path: str | None = None
    fetched_at: datetime
    http_status: int = 200


class ParsedRecord(BaseModel):
    record_type: RecordType
    district_id: UUID
    school_id: UUID | None = None
    policy_type: PolicyType | None = None
    year: int
    fields: dict
    confidence: float = 1.0
    needs_review: bool = False


class FieldChange(BaseModel):
    field_path: str
    old_value: str
    new_value: str


class ParsedEnrollment(ParsedRecord):
    record_type: RecordType = RecordType.ENROLLMENT
