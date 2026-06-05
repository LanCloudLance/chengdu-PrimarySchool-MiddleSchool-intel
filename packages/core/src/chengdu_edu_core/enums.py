from enum import StrEnum


class DistrictLevel(StrEnum):
    CORE = "core"
    EXTENDED = "extended"


class SchoolType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class SchoolLevel(StrEnum):
    PRIMARY = "primary"
    MIDDLE = "middle"
    NINE_YEAR = "nine_year"


class SourceType(StrEnum):
    GOV_WEBSITE = "gov_website"
    SCHOOL_WEBSITE = "school_website"
    WECHAT = "wechat"
    PDF = "pdf"


class ParserStrategy(StrEnum):
    RULE = "rule"
    LLM = "llm"
    HYBRID = "hybrid"


class PolicyType(StrEnum):
    SCHOOL_ENROLLMENT = "school_enrollment"
    GOV_POLICY = "gov_policy"
    DISTRICT_MAPPING = "district_mapping"


class RecordType(StrEnum):
    ENROLLMENT = "enrollment"
    PROMOTION = "promotion"


class JobStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
