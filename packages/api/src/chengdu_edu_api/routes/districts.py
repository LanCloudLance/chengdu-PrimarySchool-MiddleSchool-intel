from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from chengdu_edu_api.dependencies import get_db_session
from chengdu_edu_api.schemas import DistrictOut
from chengdu_edu_storage.orm import District

router = APIRouter(tags=["districts"])


@router.get("/districts", response_model=list[DistrictOut])
async def list_districts(
    session: AsyncSession = Depends(get_db_session),
) -> list[District]:
    result = await session.execute(select(District).order_by(District.name))
    return list(result.scalars().all())
