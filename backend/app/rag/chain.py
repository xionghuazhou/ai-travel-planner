"""RAG 知识库 Chain（Chroma 向量检索）"""
import json
import logging
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.api.types import EmbeddingFunction

from app.config import get_settings
from app.rag.embeddings import get_embedding_function

logger = logging.getLogger(__name__)
settings = get_settings()


class _ChromaEF(EmbeddingFunction):
    """适配 chromadb 的嵌入函数包装"""

    def __init__(self, fn):
        self._fn = fn

    def __call__(self, input):  # noqa: A002
        return self._fn(input)


class RAGChain:
    """RAG 知识库 Chain：景点库 + 攻略库"""

    def __init__(self):
        self.embeddings = get_embedding_function()
        self.client = chromadb.PersistentClient(path=settings.VECTOR_STORE_PATH)
        self.spot_collection = self.client.get_or_create_collection(
            name="travel_spots",
            metadata={"hnsw:space": "cosine"},
            embedding_function=_ChromaEF(self.embeddings),
        )
        self.guide_collection = self.client.get_or_create_collection(
            name="travel_guides",
            metadata={"hnsw:space": "cosine"},
            embedding_function=_ChromaEF(self.embeddings),
        )

    # ---------- 检索 ----------
    async def search_spots(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """向量检索景点"""
        if self.spot_collection.count() == 0:
            logger.warning("⚠️ 景点知识库为空")
            return []
        where = None
        if filters:
            conds = [{"city": {"$eq": v}} if k == "city" else {"category": {"$eq": v}}
                     for k, v in filters.items() if v]
            if len(conds) == 1:
                where = conds[0]
            elif len(conds) > 1:
                where = {"$and": conds}

        n = min(top_k, self.spot_collection.count())
        res = self.spot_collection.query(
            query_texts=[query], n_results=n, where=where
        )
        spots: List[Dict[str, Any]] = []
        ids = res.get("ids", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        docs = res.get("documents", [[]])[0]
        for i, _id in enumerate(ids):
            meta = metas[i] if i < len(metas) else {}
            dist = dists[i] if i < len(dists) else 1.0
            ticket = meta.get("ticket_info", "{}")
            try:
                ticket = json.loads(ticket) if isinstance(ticket, str) else (ticket or {})
            except Exception:  # noqa: BLE001
                ticket = {}
            tags = meta.get("tags", "")
            tags = [t for t in tags.split(",") if t] if isinstance(tags, str) else (tags or [])
            spots.append({
                "id": meta.get("spot_id", _id),
                "name": meta.get("name", ""),
                "name_en": meta.get("name_en"),
                "city": meta.get("city", ""),
                "country": meta.get("country", "中国"),
                "category": meta.get("category", ""),
                "address": meta.get("address", ""),
                "latitude": meta.get("latitude"),
                "longitude": meta.get("longitude"),
                "rating": meta.get("rating", 0),
                "ticket_info": ticket,
                "recommend_duration": meta.get("recommend_duration", 120),
                "tags": tags,
                "description": (docs[i] if i < len(docs) else "")[:500],
                "relevance_score": round(1 - dist, 4),
            })
        spots.sort(key=lambda x: x["relevance_score"], reverse=True)
        # 按名称+城市去重（向量库可能存在同景点多版本条目）
        seen = set()
        unique_spots = []
        for s in spots:
            key = (s["name"], s["city"])
            if key not in seen:
                seen.add(key)
                unique_spots.append(s)
        spots = unique_spots
        logger.info(f"✅ RAG 找到 {len(spots)} 个相关景点")
        return spots

    async def search_guides(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """搜索旅行攻略"""
        if self.guide_collection.count() == 0:
            return []
        n = min(top_k, self.guide_collection.count())
        res = self.guide_collection.query(query_texts=[query], n_results=n)
        guides = []
        for i, _id in enumerate(res.get("ids", [[]])[0]):
            meta = res["metadatas"][0][i] if res.get("metadatas") else {}
            guides.append({
                "id": _id,
                "title": meta.get("title", ""),
                "source": meta.get("source", ""),
                "content": (res["documents"][0][i] if res.get("documents") else ""),
                "url": meta.get("url", ""),
            })
        return guides

    # ---------- 写入 ----------
    async def add_spots(self, spots: List[Dict[str, Any]]) -> int:
        """添加景点到知识库"""
        if not spots:
            return 0
        existing = set()
        if self.spot_collection.count() > 0:
            got = self.spot_collection.get()
            existing = set(got.get("ids", []))
        docs, metas, ids = [], [], []
        for idx, spot in enumerate(spots):
            sid = str(spot.get("id") or f"spot-{idx}")
            if sid in existing:
                continue
            desc = spot.get("description", "") or ""
            tags = spot.get("tags", []) or []
            doc = (
                f"{spot.get('name','')} {spot.get('name_en','') or ''} "
                f"{spot.get('city','')} {spot.get('category','')} "
                f"{' '.join(tags) if isinstance(tags, list) else tags} {desc}"
            )
            docs.append(doc)
            ids.append(sid)
            metas.append({
                "spot_id": sid,
                "name": spot.get("name", ""),
                "name_en": spot.get("name_en") or "",
                "city": spot.get("city", ""),
                "country": spot.get("country", "中国"),
                "category": spot.get("category", ""),
                "address": spot.get("address") or "",
                "latitude": float(spot["latitude"]) if spot.get("latitude") is not None else 0.0,
                "longitude": float(spot["longitude"]) if spot.get("longitude") is not None else 0.0,
                "rating": float(spot.get("rating") or 0),
                "ticket_info": json.dumps(spot.get("ticket_info") or {}, ensure_ascii=False),
                "recommend_duration": int(spot.get("recommend_duration") or 120),
                "tags": ",".join(tags) if isinstance(tags, list) else str(tags),
            })
        if docs:
            self.spot_collection.add(documents=docs, metadatas=metas, ids=ids)
            logger.info(f"✅ 添加 {len(docs)} 个景点到知识库")
        return len(docs)

    async def add_guides(self, guides: List[Dict[str, Any]]) -> int:
        """添加攻略到知识库"""
        if not guides:
            return 0
        docs, metas, ids = [], [], []
        for idx, g in enumerate(guides):
            gid = str(g.get("id") or f"guide-{idx}")
            docs.append(g.get("content", ""))
            metas.append({
                "title": g.get("title", ""),
                "source": g.get("source", ""),
                "url": g.get("url", ""),
            })
            ids.append(gid)
        self.guide_collection.add(documents=docs, metadatas=metas, ids=ids)
        return len(docs)

    async def generate_context(
        self, destination: str, travel_style: str, duration: int
    ) -> str:
        """生成旅行上下文"""
        spots = await self.search_spots(
            query=f"{destination} {travel_style} 热门景点", top_k=10
        )
        guides = await self.search_guides(query=f"{destination} 旅游攻略 tips", top_k=3)
        context = f"**{destination} 旅行信息汇总**\n\n"
        if spots:
            context += "### 热门景点\n"
            for spot in spots[:5]:
                context += f"- {spot['name']} (评分: {spot['rating']})\n"
            context += "\n"
        if guides:
            context += "### 旅行攻略\n"
            for guide in guides[:3]:
                context += f"- {guide['title']}\n"
        return context


_rag: Optional[RAGChain] = None


def get_rag_chain() -> RAGChain:
    """获取 RAG Chain（单例）"""
    global _rag
    if _rag is None:
        _rag = RAGChain()
    return _rag
