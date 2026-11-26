"""Agent API 路由"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import run_travel_agent
from app.agent.memory import clear_history, get_conversation_history, save_message
from app.database import get_db
from app.models.user import User
from app.schemas.agent import (
    AgentMessageRequest,
    AgentMessageResponse,
    ChatHistoryResponse,
    ChatMessageOut,
    ItineraryOut,
    WeatherOut,
)
from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])
logger = logging.getLogger(__name__)


@router.post("/chat", response_model=AgentMessageResponse)
async def chat_with_agent(
    request: AgentMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """与旅行规划 Agent 对话（联网搜索 + 多阶段思考）"""
    try:
        # 加载最近对话作为上下文
        history = await get_conversation_history(str(current_user.id), db, limit=6)
        recent = [{"role": h["role"], "content": h["content"][:1500]} for h in history]

        await save_message(
            user_id=str(current_user.id), role="user",
            content=request.message, db=db,
        )

        # 运行 Agent
        result = await run_travel_agent(
            user_id=str(current_user.id),
            user_message=request.message,
            context=request.context or {},
            history=recent,
        )

        # 保存 AI 回复
        await save_message(
            user_id=str(current_user.id), role="assistant",
            content=result.get("response", ""), db=db,
            metadata={
                "intent": result.get("intent"),
                "itinerary": result.get("draft_itinerary"),
                "mode": result.get("mode"),
            },
        )

        web_sources = [
            {"title": r.get("title"), "url": r.get("url"), "source": r.get("source")}
            for r in result.get("web_results", [])
        ]
        draft = result.get("draft_itinerary")
        return AgentMessageResponse(
            message=result.get("response", ""),
            intent=result.get("intent"),
            destination=result.get("destination"),
            suggested_actions=result.get("suggested_actions", []),
            itinerary=ItineraryOut(
                content=draft.get("content", ""),
                days=draft.get("days", []),
                spots_used=draft.get("spots_used", []),
            ) if draft else None,
            weather_info=WeatherOut(**result["weather_info"])
            if result.get("weather_info") else None,
            web_sources=web_sources,
            thinking_steps=result.get("thinking_steps", []),
            mode=result.get("mode", "llm"),
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("Agent 对话失败")
        raise HTTPException(status_code=500, detail=f"Agent 处理失败: {e}")


@router.get("/history", response_model=ChatHistoryResponse)
async def get_history(
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取对话历史"""
    rows = await get_conversation_history(str(current_user.id), db, limit=limit)
    return ChatHistoryResponse(
        messages=[ChatMessageOut(
            id=r["id"], role=r["role"], content=r["content"],
            timestamp=r["timestamp"], metadata=r.get("metadata"),
        ) for r in rows],
        total=len(rows),
        has_more=len(rows) >= limit,
    )


@router.delete("/history")
async def remove_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """清空对话历史"""
    count = await clear_history(str(current_user.id), db)
    return {"message": f"已清除 {count} 条对话记录"}
