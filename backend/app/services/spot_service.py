"""景点服务"""
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spot import Spot


def _spot_dict(s: Spot) -> Dict[str, Any]:
    return {
        "id": s.id,
        "name": s.name,
        "name_en": s.name_en,
        "city": s.city,
        "country": s.country,
        "category": s.category,
        "latitude": float(s.latitude) if s.latitude is not None else None,
        "longitude": float(s.longitude) if s.longitude is not None else None,
        "address": s.address,
        "description": s.description,
        "ticket_info": s.ticket_info or {},
        "rating": float(s.rating) if s.rating is not None else 0,
        "review_count": s.review_count,
        "recommend_duration": s.recommend_duration,
        "tags": s.tags or [],
        "opening_hours": s.opening_hours or {},
        "best_season": s.best_season or [],
    }


async def list_spots(
    db: AsyncSession, city: Optional[str] = None, q: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    stmt = select(Spot)
    if city:
        stmt = stmt.where(Spot.city == city)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Spot.name.like(like), Spot.description.like(like)))
    stmt = stmt.order_by(Spot.rating.desc()).limit(limit)
    result = await db.execute(stmt)
    return [_spot_dict(s) for s in result.scalars().all()]


async def list_cities(db: AsyncSession) -> List[str]:
    result = await db.execute(select(Spot.city).distinct())
    return sorted({r[0] for r in result.all()})


async def get_spot_by_id(db: AsyncSession, spot_id: str) -> Optional[Dict[str, Any]]:
    result = await db.execute(select(Spot).where(Spot.id == spot_id))
    spot = result.scalar_one_or_none()
    return _spot_dict(spot) if spot else None
