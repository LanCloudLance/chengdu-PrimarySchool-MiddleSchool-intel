from datetime import datetime, timezone

from chengdu_edu_collectors.registry import get_collector
from chengdu_edu_core.enums import JobStatus, PolicyType
from chengdu_edu_parsers.registry import get_parser
from chengdu_edu_storage.orm import DataSource, JobRun
from chengdu_edu_storage.repository import PolicyRepository


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Pipeline:
    def __init__(self, repo: PolicyRepository):
        self.repo = repo

    async def run_source(self, source: DataSource) -> JobRun:
        run = JobRun(
            source_id=source.id,
            status=JobStatus.FAILED,
            started_at=utcnow(),
        )
        try:
            collector = get_collector(_enum_value(source.source_type))
            raw = await collector.collect(source)
            last_hash = await self.repo.get_latest_hash(source.id)
            if last_hash == raw.content_hash:
                run.status = JobStatus.SKIPPED
                return await self._finish(run)

            doc_id = await self.repo.save_raw_document(raw)
            parser = get_parser(_enum_value(source.parser_strategy))
            parsed = await parser.parse(raw, source)

            if source.district_id is None:
                raise ValueError(f"source {source.id} has no district_id")

            policy_type = parsed.policy_type or PolicyType.GOV_POLICY
            meta = getattr(source, "metadata_", None) or {}
            config_year = meta.get("data_year") if isinstance(meta, dict) else None
            year = parsed.year or config_year or utcnow().year
            existing_id = await self.repo.find_enrollment_id(
                district_id=source.district_id,
                school_id=source.school_id,
                policy_type=policy_type,
                year=year,
            )
            await self.repo.upsert_enrollment(
                district_id=source.district_id,
                school_id=source.school_id,
                policy_type=policy_type,
                year=year,
                fields=parsed.fields,
                source_doc_id=doc_id,
                confidence=parsed.confidence,
                existing_id=existing_id,
            )
            run.status = JobStatus.SUCCESS
            run.docs_fetched = 1
            run.changes_detected = 1
        except Exception as exc:
            run.error_message = str(exc)
        return await self._finish(run)

    async def _finish(self, run: JobRun) -> JobRun:
        run.finished_at = utcnow()
        return await self.repo.save_job_run(run)


def _enum_value(value) -> str:
    return value.value if hasattr(value, "value") else value
