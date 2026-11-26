"""行程 API 路由"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.trip import TripCreate, TripDetailOut, TripOut
from app.services import trip_service
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/trips", tags=["行程"])
logger = logging.getLogger(__name__)


@router.post("", response_model=TripOut)
async def create_trip(
    payload: TripCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建行程（可携带 AI 生成的结构化行程）"""
    trip = await trip_service.create_trip(
        db, str(current_user.id), payload.model_dump()
    )
    return trip


@router.get("", response_model=list[TripOut])
async def list_trips(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """我的行程列表"""
    return await trip_service.list_trips(db, str(current_user.id))


@router.get("/{trip_id}", response_model=TripDetailOut)
async def get_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """行程详情"""
    detail = await trip_service.get_trip_detail(db, str(current_user.id), trip_id)
    if not detail:
        raise HTTPException(status_code=404, detail="行程不存在")
    return detail


@router.delete("/{trip_id}")
async def delete_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除行程"""
    ok = await trip_service.delete_trip(db, str(current_user.id), trip_id)
    if not ok:
        raise HTTPException(status_code=404, detail="行程不存在")
    return {"message": "已删除"}
