import json
import os

from openai import AsyncOpenAI

from chengdu_edu_parsers.base import ParseResult

ENROLLMENT_SCHEMA = {
    "enrollment_scope": "string",
    "registration_time": "string",
    "requirements": ["string"],
    "quota": "integer|null",
    "lottery_rule": "string|null",
    "contact": "string|null",
    "notes": "string|null",
}


class LLMParser:
    REVIEW_THRESHOLD = 0.7

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.base_url = base_url or os.environ.get(
            "LLM_BASE_URL", "https://api.openai.com/v1"
        )
        self.model = model or os.environ.get("LLM_MODEL", "gpt-4o-mini")
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)

    def _build_prompt(self, raw_content: str, schema: dict) -> str:
        schema_json = json.dumps(schema, ensure_ascii=False, indent=2)
        return (
            "Extract enrollment policy fields from the document below.\n"
            f"Return a JSON object matching this schema:\n{schema_json}\n"
            "Also include a numeric confidence field (0.0-1.0) for extraction quality.\n\n"
            f"Document:\n{raw_content}"
        )

    async def parse(self, raw, source) -> ParseResult:
        prompt = self._build_prompt(raw.raw_content, ENROLLMENT_SCHEMA)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response.choices[0].message.content)
        confidence = float(data.pop("confidence", 0.8))
        return ParseResult(
            fields=data,
            confidence=confidence,
            needs_review=confidence < self.REVIEW_THRESHOLD,
        )
