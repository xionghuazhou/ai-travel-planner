"""景点 API 路由"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import spot_service

router = APIRouter(prefix="/api/v1/spots", tags=["景点"])


@router.get("")
async def list_spots(
    city: str = Query(default=None, description="城市筛选"),
    q: str = Query(default=None, description="关键词搜索"),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """景点列表/搜索"""
    return await spot_service.list_spots(db, city=city, q=q, limit=limit)


@router.get("/cities")
async def list_cities(db: AsyncSession = Depends(get_db)):
    """可用的城市列表"""
    return await spot_service.list_cities(db)
