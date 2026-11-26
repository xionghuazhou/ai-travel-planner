"""TravelAI FastAPI 入口"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import agent, auth, spots, trips
from app.config import get_settings
from app.database import init_db
from app.llm.client import get_llm_client
from app.rag.chain import get_rag_chain

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def seed_if_empty():
    """数据库与向量库为空时自动灌入景点知识库（支持增量补充）"""
    from sqlalchemy import func, select

    from app.database import AsyncSessionLocal
    from app.models.spot import Spot
    from scripts.spots_data import GUIDES, SPOTS

    async with AsyncSessionLocal() as db:
        count = (await db.execute(select(func.count(Spot.id)))).scalar() or 0
        if count == 0:
            logger.info("🌱 数据库为空，正在导入景点数据…")
            for item in SPOTS:
                db.add(Spot(**item))
            await db.commit()
            logger.info(f"✅ 已导入 {len(SPOTS)} 个景点")
        else:
            # 增量补充新景点
            existing_names = set((await db.execute(select(Spot.name))).scalars().all())
            new_items = [s for s in SPOTS if s["name"] not in existing_names]
            if new_items:
                for item in new_items:
                    db.add(Spot(**item))
                await db.commit()
                logger.info(f"✅ 增量导入 {len(new_items)} 个新景点")
            else:
                logger.info(f"数据库已有 {count} 个景点")

    rag = get_rag_chain()
    # 向量库与数据库对齐（add_spots 按 id 幂等跳过已有条目）
    async with AsyncSessionLocal() as db:
        from app.services.spot_service import _spot_dict
        rows = (await db.execute(select(Spot))).scalars().all()
        db_spots = [_spot_dict(s) for s in rows]
    if rag.spot_collection.count() < len(db_spots):
        logger.info("🌱 正在同步向量知识库索引…")
        await rag.add_spots(db_spots)
    if rag.guide_collection.count() == 0:
        await rag.add_guides(GUIDES)
        logger.info("✅ 向量知识库构建完成")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} 启动中…")
    await init_db()
    await seed_if_empty()
    # 后台探测 LLM 可用性（不阻塞启动）
    client = get_llm_client()
    if client.disabled:
        logger.warning("⚠️ 未配置 LLM_API_KEY，Agent 将使用规则化引擎")
    else:
        async def _probe():
            try:
                from app.llm.client import LLMUnavailableError
                c = get_llm_client()
                # 注意：推理模型会把小 token 预算耗尽在思考阶段，探测须给足预算
                await c.chat([{"role": "user", "content": "只回复两个字：就绪"}],
                             max_tokens=64)
            except LLMUnavailableError as e:
                logger.warning(f"⚠️ LLM 暂不可用（{e}），将使用规则化引擎兜底")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"⚠️ LLM 探测异常: {e}")
        asyncio.create_task(_probe())
    yield
    logger.info("👋 服务关闭")


settings = get_settings()
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="基于 LLM · Agent · RAG · LangGraph 的智能旅行规划系统",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(trips.router)
app.include_router(spots.router)


@app.get("/health")
async def health():
    """健康检查"""
    client = get_llm_client()
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "llm": {
            "configured": not client.disabled,
            "active_model": client.active_model,
            "last_error": client.last_error,
        },
    }
