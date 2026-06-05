from chengdu_edu_collectors.base import BaseCollector
from chengdu_edu_collectors.http import HttpCollector

_COLLECTORS: dict[str, type[BaseCollector]] = {
    "gov_website": HttpCollector,
}


def get_collector(source_type: str) -> BaseCollector:
    try:
        cls = _COLLECTORS[source_type]
    except KeyError as exc:
        raise ValueError(f"Unknown source_type: {source_type}") from exc
    return cls()
