"""异步任务示例"""
import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="tasks.warmup_knowledge_base")
def warmup_knowledge_base():
    """预热知识库（示例任务）"""
    return {"status": "ok", "message": "知识库已就绪"}
