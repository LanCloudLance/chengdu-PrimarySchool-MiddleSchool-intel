import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from chengdu_edu_core.enums import PolicyType
from chengdu_edu_parsers.base import ParseResult


class RuleParser:
    async def parse(
        self,
        raw,
        source,
        rules_path: str | None = None,
        *,
        policy_type: PolicyType | None = None,
        year: int | None = None,
    ) -> ParseResult:
        if rules_path is None:
            metadata = getattr(source, "metadata_", None) or getattr(source, "metadata", None) or {}
            rule_file = metadata.get("rule_file") if isinstance(metadata, dict) else None
            if not rule_file:
                raise ValueError("rules_path or source.metadata_.rule_file is required")
            rules_path = rule_file

        path = Path(rules_path)
        if not path.is_file():
            # 相对项目根目录 configs/
            root_candidate = Path(__file__).resolve().parents[4] / "configs" / rules_path
            if root_candidate.is_file():
                path = root_candidate
            else:
                path = Path("configs") / rules_path
        rules = yaml.safe_load(path.read_text(encoding="utf-8"))
        return self.parse_content(
            raw.raw_content,
            rules,
            policy_type=policy_type,
            year=year,
        )

    def parse_content(
        self,
        text: str,
        rules: dict,
        *,
        policy_type: PolicyType | None = None,
        year: int | None = None,
    ) -> ParseResult:
        fields: dict[str, str] = {}
        for name, rule in rules["fields"].items():
            scope = text
            if "selector" in rule:
                soup = BeautifulSoup(text, "html.parser")
                element = soup.select_one(rule["selector"])
                scope = element.get_text("\n", strip=True) if element else text
            if "regex" in rule:
                match = re.search(rule["regex"], scope, re.DOTALL)
                if match:
                    fields[name] = match.group(1).strip()

        return ParseResult(
            fields=fields,
            confidence=1.0,
            needs_review=False,
            policy_type=policy_type,
            year=year,
        )
