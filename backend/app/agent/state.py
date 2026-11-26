"""Agent 状态定义"""
from enum import Enum
from typing import Any, Dict, List, Optional, TypedDict


class IntentType(str, Enum):
    """旅行意图类型"""
    TRIP_PLAN = "trip_plan"           # 行程规划
    SPOT_QUERY = "spot_query"         # 景点查询
    MODIFY_TRIP = "modify_trip"       # 修改行程
    BOOKING_QUERY = "booking_query"   # 预订查询
    WEATHER_QUERY = "weather_query"   # 天气查询
    BUDGET_QUERY = "budget_query"     # 预算查询
    TIPS_QUERY = "tips_query"         # 旅行 tips
    CHITCHAT = "chitchat"             # 闲聊


class TripStatus(str, Enum):
    """行程状态"""
    PLANNING = "planning"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TravelStyle(str, Enum):
    """旅行风格"""
    RELAXED = "relaxed"
    ADVENTUROUS = "adventurous"
    CULTURAL = "cultural"
    FAMILY = "family"
    ROMANTIC = "romantic"
    BUSINESS = "business"
    FOODIE = "foodie"
    PHOTOGRAPHY = "photography"


class AgentState(TypedDict):
    """
    Agent 状态定义：规划过程中所有需要传递的数据
    """
    # 用户输入
    user_id: str
    user_message: str

    # 意图识别
    intent: Optional[str]
    intent_confidence: float

    # 旅行需求解析
    destination: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    budget: Optional[int]
    travelers: Optional[int]
    travel_style: Optional[str]

    # 检索结果
    retrieved_spots: List[Dict[str, Any]]
    retrieved_guides: List[Dict[str, Any]]
    weather_info: Optional[Dict[str, Any]]

    # 联网搜索
    search_queries: List[str]
    web_results: List[Dict[str, Any]]

    # 行程规划
    draft_itinerary: Optional[Dict[str, Any]]
    optimized_itinerary: Optional[Dict[str, Any]]
    reflection: Optional[Dict[str, Any]]

    # 对话历史
    messages: List[Dict[str, str]]

    # 输出
    response: Optional[str]
    suggested_actions: List[str]
    thinking_steps: List[Dict[str, Any]]
    unverified_spots: List[str]

    # 错误处理
    error: Optional[str]
    retry_count: int
