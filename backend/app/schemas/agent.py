"""Agent 相关 Pydantic 模型"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentMessageRequest(BaseModel):
    """Agent 消息请求"""
    message: str = Field(..., min_length=1, max_length=2000, description="用户消息")
    context: Optional[Dict[str, Any]] = Field(default={}, description="上下文数据")


class ItinerarySpotOut(BaseModel):
    """行程中的景点"""
    name: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_minutes: int = 120
    category: Optional[str] = None
    notes: Optional[str] = None
    estimated_cost: int = 0


class ItineraryDayOut(BaseModel):
    """行程单日"""
    day_number: int
    date: Optional[str] = None
    theme: Optional[str] = None
    summary: Optional[str] = None
    weather_info: Optional[Dict[str, Any]] = None
    spots: List[ItinerarySpotOut] = []


class ItineraryOut(BaseModel):
    """结构化行程"""
    content: str = Field(default="", description="行程 Markdown 文本")
    days: List[ItineraryDayOut] = []
    spots_used: List[str] = []


class WeatherOut(BaseModel):
    """天气信息"""
    city: str
    forecasts: List[Dict[str, Any]] = []
    tips: Optional[str] = None


class AgentMessageResponse(BaseModel):
    """Agent 消息响应"""
    message: str = Field(..., description="AI 回复内容")
    intent: Optional[str] = Field(default=None, description="识别的意图")
    destination: Optional[str] = Field(default=None, description="目的地")
    suggested_actions: List[str] = Field(default=[], description="建议的操作")
    itinerary: Optional[ItineraryOut] = Field(default=None, description="生成的行程")
    weather_info: Optional[WeatherOut] = Field(default=None, description="天气信息")
    web_sources: List[Dict[str, Any]] = Field(default=[], description="联网搜索引用来源")
    thinking_steps: List[Dict[str, Any]] = Field(default=[], description="Agent 思考过程")
    mode: str = Field(default="llm", description="llm / fallback 模式")


class ChatMessageOut(BaseModel):
    """对话消息"""
    id: str
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


class ChatHistoryResponse(BaseModel):
    """对话历史响应"""
    messages: List[ChatMessageOut]
    total: int
    has_more: bool
