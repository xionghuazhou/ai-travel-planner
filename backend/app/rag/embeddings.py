"""嵌入模型：本地哈希嵌入（零依赖、离线可用）+ OpenAI 兼容远程嵌入"""
import hashlib
import math
import re
from typing import List

import httpx

from app.config import get_settings

DIM = 512


class LocalHashEmbedding:
    """字符 n-gram 哈希嵌入：无需模型下载，中文检索效果可用"""

    def __init__(self, dim: int = DIM):
        self.dim = dim

    def _embed_one(self, text: str) -> List[float]:
        vec = [0.0] * self.dim
        t = re.sub(r"\s+", "", (text or "").lower())
        grams = list(t)
        grams += [t[i:i + 2] for i in range(len(t) - 1)]
        grams += [t[i:i + 3] for i in range(len(t) - 2)]
        for g in grams:
            if not g:
                continue
            h = int(hashlib.md5(g.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 128) % 2 == 0 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def __call__(self, input: List[str]) -> List[List[float]]:  # noqa: A002
        return [self._embed_one(x) for x in input]


class OpenAICompatEmbedding:
    """OpenAI 兼容 /embeddings 接口"""

    def __init__(self, base_url: str, api_key: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._fallback = LocalHashEmbedding()
        self._broken = False

    def _remote(self, texts: List[str]) -> List[List[float]]:
        resp = httpx.post(
            f"{self.base_url}/embeddings",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "input": texts},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [item["embedding"] for item in data["data"]]

    def __call__(self, input: List[str]) -> List[List[float]]:  # noqa: A002
        if self._broken:
            return self._fallback(input)
        try:
            return self._remote(input)
        except Exception:  # noqa: BLE001
            self._broken = True
            return self._fallback(input)


def get_embedding_function():
    """按配置返回嵌入函数；远程不可用时自动回退本地"""
    s = get_settings()
    if s.EMBEDDING_PROVIDER == "openai" and s.LLM_API_KEY:
        return OpenAICompatEmbedding(s.LLM_BASE_URL, s.LLM_API_KEY, s.EMBEDDING_MODEL)
    return LocalHashEmbedding()
