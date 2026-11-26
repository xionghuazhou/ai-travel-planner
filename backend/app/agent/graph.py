"""LangGraph Agent 图构建"""
import logging
from typing import Any, Dict

from langgraph.graph import END, StateGraph

from app.agent.nodes import (
    fetch_weather,
    generate_itinerary,
    generate_response,
    optimize_route,
    parse_requirements,
    reflect,
    route_after_parse,
    route_after_reflect,
    search_spots,
    web_search,
)
from app.agent.state import AgentState

logger = logging.getLogger(__name__)


def create_travel_agent_graph() -> Any:
    """
    创建旅行规划 Agent 图

    工作流：
    解析需求 → (意图路由) → 检索景点 → 获取天气 → 联网搜索 → 生成行程
            → 反思检查 → (不通过则重新生成一次) → 路线优化 → 生成回复
    """
    graph = StateGraph(AgentState)

    # 添加节点
    graph.add_node("parse_requirements", parse_requirements)
    graph.add_node("search_spots", search_spots)
    graph.add_node("fetch_weather", fetch_weather)
    graph.add_node("web_search", web_search)
    graph.add_node("generate_itinerary", generate_itinerary)
    graph.add_node("reflect", reflect)
    graph.add_node("optimize_route", optimize_route)
    graph.add_node("generate_response", generate_response)

    # 设置入口
    graph.set_entry_point("parse_requirements")

    # 意图路由：闲聊直接回复；规划需求走完整流程
    graph.add_conditional_edges(
        "parse_requirements",
        route_after_parse,
        {"direct_reply": "generate_response", "plan_trip": "search_spots"},
    )

    # 主干流程
    graph.add_edge("search_spots", "fetch_weather")
    graph.add_edge("fetch_weather", "web_search")
    graph.add_edge("web_search", "generate_itinerary")
    graph.add_edge("generate_itinerary", "reflect")

    # 反思路由：不通过且未重试过 → 重新生成；否则优化路线
    graph.add_conditional_edges(
        "reflect",
        route_after_reflect,
        {"retry": "generate_itinerary", "continue": "optimize_route"},
    )

    graph.add_edge("optimize_route", "generate_response")
    graph.add_edge("generate_response", END)

    compiled = graph.compile()
    logger.info("✅ TravelAI Agent 图构建完成")
    return compiled


# 全局 Agent 实例
_travel_agent = None


def get_travel_agent():
    """获取 Agent 实例（单例）"""
    global _travel_agent
    if _travel_agent is None:
        _travel_agent = create_travel_agent_graph()
    return _travel_agent


async def run_travel_agent(
    user_id: str,
    user_message: str,
    context: dict = None,
    history: list = None,
) -> dict:
    """运行旅行规划 Agent"""
    logger.info(f"🚀 [Agent] 开始处理用户请求: {user_message[:50]}...")

    initial_state: AgentState = {
        "user_id": user_id,
        "user_message": user_message,
        "intent": None,
        "intent_confidence": 0.0,
        "destination": None,
        "start_date": None,
        "end_date": None,
        "budget": None,
        "travelers": None,
        "travel_style": None,
        "retrieved_spots": [],
        "retrieved_guides": [],
        "weather_info": None,
        "search_queries": [],
        "web_results": [],
        "draft_itinerary": None,
        "optimized_itinerary": None,
        "reflection": None,
        "messages": history or [],
        "response": None,
        "suggested_actions": [],
        "thinking_steps": [],
        "unverified_spots": [],
        "error": None,
        "retry_count": 0,
    }

    # 注入上下文
    if context:
        for key, value in context.items():
            if key in initial_state:
                initial_state[key] = value

    agent = get_travel_agent()
    result = await agent.ainvoke(initial_state)
    logger.info("✅ [Agent] 处理完成")

    return {
        "response": result.get("response"),
        "intent": result.get("intent"),
        "destination": result.get("destination"),
        "suggested_actions": result.get("suggested_actions", []),
        "weather_info": result.get("weather_info"),
        "draft_itinerary": result.get("draft_itinerary"),
        "optimized_itinerary": result.get("optimized_itinerary"),
        "web_results": result.get("web_results", []),
        "thinking_steps": result.get("thinking_steps", []),
        "mode": (result.get("draft_itinerary") or {}).get("generated_by", "llm"),
    }
