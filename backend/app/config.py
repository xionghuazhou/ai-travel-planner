"""应用程序配置"""
from functools import lru_cache
from typing import Optional, List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # 应用基础配置
    APP_NAME: str = "TravelAI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库配置（开发默认 SQLite，Docker 中由环境变量覆盖为 PostgreSQL）
    DATABASE_URL: str = "sqlite+aiosqlite:///./travelai.db"

    # Redis 配置
    REDIS_URL: str = "redis://localhost:6379/0"

    # JWT 配置
    SECRET_KEY: str = "travelai-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 天

    # ===== LLM 配置（OpenAI 兼容协议，支持中转站）=====
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: str = "https://api.sensenova.cn/compatible-mode/v1"
    # 首选模型；启动时会按 LLM_MODEL_CANDIDATES 依次探测可用的模型
    LLM_MODEL: str = "DeepSeek-V4-Flash"
    LLM_MODEL_CANDIDATES: str = (
        "DeepSeek-V4-Flash,DeepSeek V4 Flash,deepseek-v4-flash,"
        "DeepSeek-V3.1,deepseek-v3,deepseek-chat,gpt-4o-mini,SenseChat-5"
    )
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 16384
    LLM_TIMEOUT: int = 90

    # ===== RAG 配置 =====
    EMBEDDING_PROVIDER: str = "local"  # local: 本地哈希词嵌；openai: OpenAI 兼容 /embeddings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VECTOR_STORE_TYPE: str = "chroma"
    VECTOR_STORE_PATH: str = "./data/vectorstore"

    # ===== 外部 API 配置 =====
    AMAP_API_KEY: Optional[str] = None  # 高德地图
    WEATHER_API_KEY: Optional[str] = None  # 天气 API（留空则使用模拟数据）
    SEARCH_BACKEND: str = "auto"  # auto: bing_cn -> duckduckgo 自动切换
    SEARCH_TIMEOUT: int = 12

    # CORS 配置
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080"

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def llm_model_candidates(self) -> List[str]:
        names = [m.strip() for m in self.LLM_MODEL_CANDIDATES.split(",") if m.strip()]
        if self.LLM_MODEL and self.LLM_MODEL not in names:
            names.insert(0, self.LLM_MODEL)
        return names

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """获取配置（单例）"""
    return Settings()
