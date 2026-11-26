"""行程数据模型"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Trip(Base):
    """行程模型"""
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)

    # 行程基本信息
    title: Mapped[str] = mapped_column(String(200))
    destination: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[str] = mapped_column(String(20))
    end_date: Mapped[str] = mapped_column(String(20))
    budget: Mapped[int] = mapped_column(Integer, default=0)
    travelers: Mapped[int] = mapped_column(Integer, default=1)

    # 状态与需求
    status: Mapped[str] = mapped_column(String(20), default="planning")
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    generated_plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关系
    user = relationship("User", back_populates="trips")
    days = relationship("ItineraryDay", back_populates="trip", cascade="all, delete-orphan")

    @property
    def duration_days(self) -> int:
        """行程天数"""
        from datetime import date
        d1 = date.fromisoformat(self.start_date)
        d2 = date.fromisoformat(self.end_date)
        return (d2 - d1).days + 1


class ItineraryDay(Base):
    """每日行程"""
    __tablename__ = "itinerary_days"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey("trips.id"), index=True)

    day_number: Mapped[int] = mapped_column(Integer)
    date: Mapped[str] = mapped_column(String(20))
    theme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    weather_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    trip = relationship("Trip", back_populates="days")
    spots = relationship("ItinerarySpot", back_populates="day", cascade="all, delete-orphan")


class ItinerarySpot(Base):
    """行程中的景点"""
    __tablename__ = "itinerary_spots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    day_id: Mapped[str] = mapped_column(String(36), ForeignKey("itinerary_days.id"), index=True)
    spot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    name: Mapped[str] = mapped_column(String(200), default="")
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    start_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=120)
    transport_to_next: Mapped[str | None] = mapped_column(String(100), nullable=True)
    estimated_cost: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    day = relationship("ItineraryDay", back_populates="spots")
