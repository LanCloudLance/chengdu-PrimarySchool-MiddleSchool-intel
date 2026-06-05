from typing import Protocol

from chengdu_edu_core.models import RawDocument


class BaseCollector(Protocol):
    source_type: str

    async def collect(self, source) -> RawDocument: ...
