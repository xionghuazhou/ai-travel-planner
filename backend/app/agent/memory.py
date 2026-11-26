"""Agent 对话记忆管理"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatMessage

logger = logging.getLogger(__name__)


async def save_message(
    user_id: str,
    role: str,
    content: str,
    db: AsyncSession,
    metadata: Optional[Dict[str, Any]] = None,
) -> ChatMessage:
    """保存对话消息"""
    msg = ChatMessage(
        user_id=user_id,
        role=role,
        content=content,
        metadata_json=metadata or {},
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


async def get_conversation_history(
    user_id: str,
    db: AsyncSession,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """获取对话历史（时间正序）"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    rows.reverse()
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "timestamp": m.created_at.isoformat() if m.created_at else None,
            "metadata": m.metadata_json or {},
        }
        for m in rows
    ]


async def get_recent_messages(
    user_id: str,
    db: AsyncSession,
    limit: int = 6,
) -> List[Dict[str, str]]:
    """获取最近 N 条消息（用于 LLM 上下文）"""
    history = await get_conversation_history(user_id, db, limit=limit)
    return [{"role": h["role"], "content": h["content"][:1500]} for h in history]


async def clear_history(user_id: str, db: AsyncSession) -> int:
    """清空对话历史"""
    result = await db.execute(
        delete(ChatMessage).where(ChatMessage.user_id == user_id)
    )
    await db.commit()
    return result.rowcount or 0
