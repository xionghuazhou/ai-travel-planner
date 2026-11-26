"""景点搜索工具"""
import logging
from typing import Any, Dict, List, Optional

from app.rag.chain import get_rag_chain

logger = logging.getLogger(__name__)


class SpotSearchTool:
    """景点搜索工具"""

    def __init__(self):
        self.rag = get_rag_chain()

    async def search(
        self,
        query: str,
        city: Optional[str] = None,
        category: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索景点（向量检索 + 城市过滤）"""
        search_query = f"{city} {query}" if city else query
        filters = {"city": city, "category": category} if (city or category) else None
        results = await self.rag.search_spots(
            query=search_query, top_k=top_k,
            filters=filters if (city or category) else None,
        )
        if not results and city:
            # 城市过滤无结果时放宽
            results = await self.rag.search_spots(query=search_query, top_k=top_k)
        return results

    async def get_recommendations(
        self, city: str, style: str = "relaxed", limit: int = 10
    ) -> List[Dict[str, Any]]:
        """按旅行风格获取景点推荐"""
        style_keywords = {
            "relaxed": "休闲 放松 舒适",
            "adventurous": "刺激 冒险 挑战 户外",
            "cultural": "历史 文化 博物馆 古迹",
            "family": "亲子 儿童 家庭 游乐园",
            "romantic": "浪漫 情侣 约会 夜景",
            "foodie": "美食 小吃 街道 市集",
            "photography": "风景 拍照 日出 观景",
            "business": "商圈 展览 地标",
        }
        keywords = style_keywords.get(style, "")
        query = f"{city} {keywords} 必去景点".strip()
        return await self.search(query, city=city, top_k=limit)


class SpotTool:
    """景点工具（LangChain Tool 风格封装）"""

    name = "search_spots"
    description = (
        "搜索热门景点信息。当用户询问某地的景点、必去的地方、推荐游览的地方时使用。"
        "输入：目的地城市和偏好（如：亲子、浪漫、美食等）"
    )

    async def run(self, city: str, preference: str = "") -> str:
        tool = SpotSearchTool()
        spots = await tool.get_recommendations(city=city, style=preference or "relaxed", limit=10)
        if not spots:
            return f"抱歉，没有找到 {city} 相关的景点信息。"
        result = f"**{city} 热门景点推荐：**\n\n"
        for i, spot in enumerate(spots, 1):
            result += f"{i}. **{spot['name']}**\n"
            result += f"   📍 {spot.get('address') or '地址未知'}\n"
            result += f"   ⭐ 评分: {spot.get('rating', 'N/A')}\n"
            result += f"   ⏱️ 建议游览: {spot.get('recommend_duration', 120)}分钟\n\n"
        return result
