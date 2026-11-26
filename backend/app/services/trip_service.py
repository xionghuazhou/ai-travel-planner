"""行程服务"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.spot import Spot
from app.models.trip import ItineraryDay, ItinerarySpot, Trip

logger = logging.getLogger(__name__)


async def create_trip(db: AsyncSession, user_id: str, payload: Dict[str, Any]) -> Trip:
    """创建行程（可含结构化每日行程）"""
    trip = Trip(
        user_id=user_id,
        title=payload.get("title") or f"{payload['destination']}之旅",
        destination=payload["destination"],
        start_date=payload["start_date"],
        end_date=payload["end_date"],
        budget=payload.get("budget") or 0,
        travelers=payload.get("travelers") or 1,
        requirements=payload.get("requirements") or {},
        status="confirmed",
    )
    db.add(trip)
    await db.flush()

    days = payload.get("days") or []
    if not days and payload.get("markdown"):
        days = _parse_markdown_days(payload["markdown"], payload["destination"],
                                    payload["start_date"])
    for d in days:
        day = ItineraryDay(
            trip_id=trip.id,
            day_number=d.get("day_number") or (len(days) and 1) or 1,
            date=d.get("date") or payload["start_date"],
            theme=d.get("theme"),
            summary=d.get("summary"),
            weather_info=d.get("weather_info"),
        )
        db.add(day)
        await db.flush()
        for idx, s in enumerate(d.get("spots", [])):
            db.add(ItinerarySpot(
                day_id=day.id,
                name=s.get("name", ""),
                order_index=idx,
                start_time=s.get("start_time"),
                end_time=s.get("end_time"),
                duration_minutes=s.get("duration_minutes") or 120,
                transport_to_next=s.get("transport_to_next"),
                estimated_cost=s.get("estimated_cost") or 0,
                category=s.get("category"),
                notes=s.get("notes"),
            ))
    await db.commit()

    result = await db.execute(
        select(Trip).options(selectinload(Trip.days)).where(Trip.id == trip.id)
    )
    return result.scalar_one()


def _parse_markdown_days(markdown: str, destination: str, start_date: str) -> List[Dict[str, Any]]:
    """从 Markdown 粗略解析每日行程（兜底）"""
    days: List[Dict[str, Any]] = []
    sections = __import__("re").split(r"\n##\s*Day\s*(\d+)", markdown)
    i = 1
    while i + 1 < len(sections) + 1 and i < len(sections):
        num = sections[i]
        body = sections[i + 1] if i + 1 < len(sections) else ""
        days.append({
            "day_number": int(num),
            "date": start_date,
            "theme": body.split("\n")[0][:50].strip(" ·"),
            "summary": body[:200],
            "spots": [],
        })
        i += 2
    return days


async def get_trip_detail(db: AsyncSession, user_id: str, trip_id: str) -> Optional[Dict[str, Any]]:
    """获取行程详情（含每日景点）"""
    result = await db.execute(
        select(Trip)
        .options(selectinload(Trip.days).selectinload(ItineraryDay.spots))
        .where(Trip.id == trip_id, Trip.user_id == user_id)
    )
    trip = result.scalar_one_or_none()
    if not trip:
        return None
    days = []
    for d in sorted(trip.days, key=lambda x: x.day_number):
        days.append({
            "id": d.id,
            "day_number": d.day_number,
            "date": d.date,
            "theme": d.theme,
            "summary": d.summary,
            "weather_info": d.weather_info,
            "spots": [
                {
                    "id": s.id,
                    "name": s.name,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "duration_minutes": s.duration_minutes,
                    "transport_to_next": s.transport_to_next,
                    "estimated_cost": s.estimated_cost,
                    "category": s.category,
                    "notes": s.notes,
                }
                for s in sorted(d.spots, key=lambda x: x.order_index)
            ],
        })
    return {
        "id": trip.id,
        "title": trip.title,
        "destination": trip.destination,
        "start_date": trip.start_date,
        "end_date": trip.end_date,
        "budget": trip.budget,
        "travelers": trip.travelers,
        "status": trip.status,
        "requirements": trip.requirements or {},
        "created_at": trip.created_at,
        "days": days,
    }


async def list_trips(db: AsyncSession, user_id: str) -> List[Dict[str, Any]]:
    result = await db.execute(
        select(Trip).where(Trip.user_id == user_id).order_by(Trip.created_at.desc())
    )
    return [
        {
            "id": t.id,
            "title": t.title,
            "destination": t.destination,
            "start_date": t.start_date,
            "end_date": t.end_date,
            "budget": t.budget,
            "travelers": t.travelers,
            "status": t.status,
            "created_at": t.created_at,
        }
        for t in result.scalars().all()
    ]


async def delete_trip(db: AsyncSession, user_id: str, trip_id: str) -> bool:
    result = await db.execute(
        select(Trip).where(Trip.id == trip_id, Trip.user_id == user_id)
    )
    trip = result.scalar_one_or_none()
    if not trip:
        return False
    await db.delete(trip)
    await db.commit()
    return True
