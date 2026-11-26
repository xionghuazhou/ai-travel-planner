"""行程相关 Pydantic 模型"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ItinerarySpotIn(BaseModel):
    """保存行程时的景点"""
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: int = 120
    category: Optional[str] = None
    notes: Optional[str] = None
    estimated_cost: int = 0


class ItineraryDayIn(BaseModel):
    """保存行程时的单日"""
    day_number: int
    date: Optional[str] = None
    theme: Optional[str] = None
    summary: Optional[str] = None
    weather_info: Optional[Dict[str, Any]] = None
    spots: List[ItinerarySpotIn] = []


class TripCreate(BaseModel):
    """创建行程"""
    title: Optional[str] = None
    destination: str = Field(..., min_length=1, max_length=200)
    start_date: str = Field(..., description="YYYY-MM-DD")
    end_date: str = Field(..., description="YYYY-MM-DD")
    budget: int = 0
    travelers: int = 1
    requirements: Dict[str, Any] = Field(default={})
    days: List[ItineraryDayIn] = []
    markdown: Optional[str] = None


class TripOut(BaseModel):
    """行程信息"""
    id: str
    title: str
    destination: str
    start_date: str
    end_date: str
    budget: int
    travelers: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TripDetailOut(TripOut):
    """行程详情（含每日行程）"""
    requirements: Dict[str, Any] = {}
    generated_plan: Optional[Dict[str, Any]] = None
    days: List[Dict[str, Any]] = []
