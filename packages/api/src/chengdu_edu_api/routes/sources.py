from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.schemas import DataSourceOut, DataSourcePatch, StatsOut
from chengdu_edu_storage.orm import (
    DataSource,
    District,
    EnrollmentPolicy,
    JobRun,
    PromotionPolicy,
    School,
)

router = APIRouter(tags=["sources", "stats"])


@router.get("/sources", response_model=list[DataSourceOut])
async def list_sources(
    session: AsyncSession = Depends(get_db_session),
) -> list[DataSource]:
    result = await session.execute(select(DataSource).order_by(DataSource.name))
    return list(result.scalars().all())


@router.patch("/sources/{source_id}", response_model=DataSourceOut)
async def patch_source(
    source_id: UUID,
    body: DataSourcePatch,
    session: AsyncSession = Depends(get_db_session),
) -> DataSource:
    source = await session.get(DataSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    source.is_active = body.is_active
    await session.commit()
    await session.refresh(source)
    return source


@router.get("/stats", response_model=StatsOut)
async def get_stats(
    session: AsyncSession = Depends(get_db_session),
) -> StatsOut:
    districts = (await session.execute(select(func.count()).select_from(District))).scalar_one()
    schools = (await session.execute(select(func.count()).select_from(School))).scalar_one()
    sources = (await session.execute(select(func.count()).select_from(DataSource))).scalar_one()
    active_sources = (
        await session.execute(
            select(func.count()).select_from(DataSource).where(DataSource.is_active.is_(True))
        )
    ).scalar_one()
    enrollment_policies = (
        await session.execute(select(func.count()).select_from(EnrollmentPolicy))
    ).scalar_one()
    promotion_policies = (
        await session.execute(select(func.count()).select_from(PromotionPolicy))
    ).scalar_one()
    job_runs = (await session.execute(select(func.count()).select_from(JobRun))).scalar_one()

    return StatsOut(
        districts=districts,
        schools=schools,
        sources=sources,
        active_sources=active_sources,
        enrollment_policies=enrollment_policies,
        promotion_policies=promotion_policies,
        job_runs=job_runs,
    )
