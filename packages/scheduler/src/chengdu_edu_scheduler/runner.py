import argparse
import asyncio
import logging
import os
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from chengdu_edu_scheduler.pipeline import Pipeline
from chengdu_edu_storage.db import SessionLocal
from chengdu_edu_storage.orm import DataSource
from chengdu_edu_storage.repository import PolicyRepository

logger = logging.getLogger(__name__)


class SchedulerRunner:
    def __init__(self, pipeline: Pipeline, sources: list[DataSource]):
        self.pipeline = pipeline
        self.sources = sources
        self.scheduler = AsyncIOScheduler()

    def register_sources(self, sources: list[DataSource]) -> None:
        for source in sources:
            if source.is_active:
                self.scheduler.add_job(
                    self.pipeline.run_source,
                    CronTrigger.from_crontab(source.schedule),
                    args=[source],
                    id=str(source.id),
                    replace_existing=True,
                )

    def start(self) -> None:
        self.scheduler.start()

    async def trigger(self, scope: str, target_id: UUID | None = None) -> None:
        if scope == "all":
            for source in self.sources:
                await self.pipeline.run_source(source)
        elif scope == "source" and target_id:
            source = await self.pipeline.repo.get_source(target_id)
            if source is None:
                raise ValueError(f"source not found: {target_id}")
            await self.pipeline.run_source(source)
        else:
            raise ValueError(f"invalid trigger scope: {scope}")


def _scheduler_enabled() -> bool:
    return os.environ.get("SCHEDULER_ENABLED", "true").lower() == "true"


async def _run_trigger(scope: str, target_id: UUID | None) -> None:
    async with SessionLocal() as session:
        repo = PolicyRepository(session)
        pipeline = Pipeline(repo)
        sources = await repo.list_active_sources()
        runner = SchedulerRunner(pipeline, sources)
        await runner.trigger(scope, target_id)


async def _run_daemon() -> None:
    async with SessionLocal() as session:
        repo = PolicyRepository(session)
        pipeline = Pipeline(repo)
        sources = await repo.list_active_sources()
        runner = SchedulerRunner(pipeline, sources)
        runner.register_sources(sources)
        runner.start()
        logger.info("scheduler started with %d active source(s)", len(sources))
        await asyncio.Event().wait()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Chengdu edu intelligence scheduler")
    parser.add_argument(
        "--trigger",
        choices=["all", "source"],
        help="manually run pipeline for all active sources or one source",
    )
    parser.add_argument("--id", type=UUID, help="source UUID (required for --trigger source)")
    args = parser.parse_args()

    if args.trigger:
        if args.trigger == "source" and args.id is None:
            parser.error("--id is required when --trigger source")
        asyncio.run(_run_trigger(args.trigger, args.id))
        return

    if not _scheduler_enabled():
        logger.info("SCHEDULER_ENABLED=false; exiting without starting scheduler")
        return

    try:
        asyncio.run(_run_daemon())
    except KeyboardInterrupt:
        logger.info("scheduler stopped")


if __name__ == "__main__":
    main()
