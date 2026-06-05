from chengdu_edu_parsers.llm_parser import LLMParser
from chengdu_edu_parsers.rule_parser import RuleParser

_PARSERS: dict[str, type] = {
    "rule": RuleParser,
    "llm": LLMParser,
}


def get_parser(strategy: str):
    try:
        cls = _PARSERS[strategy]
    except KeyError as exc:
        raise ValueError(f"Unknown parser_strategy: {strategy}") from exc
    return cls()
