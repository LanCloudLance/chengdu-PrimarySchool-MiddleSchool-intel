from pydantic import BaseModel

from chengdu_edu_core.enums import PolicyType


class ParseResult(BaseModel):
    fields: dict
    confidence: float = 1.0
    needs_review: bool = False
    policy_type: PolicyType | None = None
    year: int | None = None
