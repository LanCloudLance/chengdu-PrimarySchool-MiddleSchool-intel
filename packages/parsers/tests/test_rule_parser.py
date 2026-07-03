from pathlib import Path

import yaml

from chengdu_edu_core.enums import PolicyType
from chengdu_edu_parsers.rule_parser import RuleParser

ROOT = Path(__file__).resolve().parents[3]


def test_rule_parser_extracts_fields_from_html():
    html = (ROOT / "packages/parsers/tests/fixtures/jinjiang_sample.html").read_text(
        encoding="utf-8"
    )
    rules = yaml.safe_load(
        (ROOT / "configs/source_rules/jinjiang_gov.yaml").read_text(encoding="utf-8")
    )
    parser = RuleParser()
    result = parser.parse_content(
        html, rules, policy_type=PolicyType.GOV_POLICY, year=2026
    )
    assert "东大街" in result.fields["enrollment_scope"]
    assert result.fields["registration_time"] == "2026-03-01 ~ 2026-03-15"
    assert result.fields["contact"] == "028-8665-1234"
    assert result.confidence == 1.0
    assert result.needs_review is False
    assert result.policy_type == PolicyType.GOV_POLICY
    assert result.year == 2026
