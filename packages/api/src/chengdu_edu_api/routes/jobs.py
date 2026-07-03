from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_scheduler.pipeline import Pipeline
from chengdu_edu_scheduler.runner import SchedulerRunner
from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.schemas import JobRunOut, JobTriggerRequest, JobTriggerResponse, PaginatedJobRuns
from chengdu_edu_storage.orm import JobRun
from chengdu_edu_storage.repository import PolicyRepository

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/trigger", response_model=JobTriggerResponse)
async def trigger_job(
    body: JobTriggerRequest,
    session: AsyncSession = Depends(get_db_session),
) -> JobTriggerResponse:
    if body.scope not in {"all", "source"}:
        raise HTTPException(status_code=400, detail="scope must be 'all' or 'source'")
    if body.scope == "source" and body.target_id is None:
        raise HTTPException(status_code=400, detail="target_id required for source scope")

    repo = PolicyRepository(session)
    pipeline = Pipeline(repo)
    sources = await repo.list_active_sources()
    runner = SchedulerRunner(pipeline, sources)

    try:
        await runner.trigger(body.scope, body.target_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JobTriggerResponse(status="triggered", scope=body.scope, target_id=body.target_id)


@router.get("/runs", response_model=PaginatedJobRuns)
async def list_job_runs(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedJobRuns:
    total = (await session.execute(select(func.count()).select_from(JobRun))).scalar_one()
    stmt = (
        select(JobRun)
        .order_by(JobRun.started_at.desc())
        .offset(offset)
        .limit(limit)
    )
    runs = list((await session.execute(stmt)).scalars().all())
    return PaginatedJobRuns(
        items=[JobRunOut.model_validate(run) for run in runs],
        total=total,
        offset=offset,
        limit=limit,
    )
