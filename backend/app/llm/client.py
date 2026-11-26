"""LLM 客户端（OpenAI 兼容协议，支持中转站）

启动时按候选模型列表自动探测可用模型；全部失败时进入降级模式，
Agent 会使用基于 RAG 检索的规则化生成兜底。
"""
import asyncio
import logging
import re
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


def _is_quota_error(err: str) -> bool:
    """是否为配额/限流错误（免费档常为每分钟限流，短暂即可恢复）"""
    lowered = (err or "").lower()
    return any(k in lowered for k in ("quota", "allocated", "insufficient", "429"))


def _is_retryable(err: str) -> bool:
    """瞬时错误（限流/配额/空响应/超时）可退避重试"""
    lowered = (err or "").lower()
    return any(k in lowered for k in ("429", "quota", "allocated", "insufficient",
                                      "rate", "empty", "timeout", "timed out"))


class LLMUnavailableError(Exception):
    """LLM 完全不可用（网络/鉴权失败）"""


class LLMClient:
    """OpenAI 兼容 Chat Completions 客户端"""

    def __init__(self):
        s = get_settings()
        self.api_key = s.LLM_API_KEY or ""
        self.base_url = (s.LLM_BASE_URL or "").rstrip("/")
        self.temperature = s.LLM_TEMPERATURE
        self.max_tokens = s.LLM_MAX_TOKENS
        self.timeout = s.LLM_TIMEOUT
        self.candidates: List[str] = s.llm_model_candidates
        self.active_model: Optional[str] = None  # 探测成功的模型
        self.disabled = not bool(self.api_key)   # 未配置 Key 时直接降级
        self._errors: Dict[str, str] = {}        # 各模型的最近错误
        self._quota_cooldown_until: float = 0.0  # 配额用尽后的冷却截止时间戳

    @property
    def last_error(self) -> Optional[str]:
        """优先展示首选模型的错误（诊断最相关）"""
        preferred = self.candidates[0] if self.candidates else None
        if preferred and preferred in self._errors:
            return self._errors[preferred]
        if self._errors:
            return next(iter(self._errors.values()))
        return None

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _chat_once(self, model: str, messages: List[Dict[str, str]],
                         temperature: float, max_tokens: int,
                         json_mode: bool = False) -> str:
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code == 200:
                data = resp.json()
                msg = data["choices"][0]["message"]
                content = msg.get("content") or ""
                # 推理模型思考可能耗尽输出预算导致 content 为空，此时回退到思考内容中提取答案
                if not content.strip():
                    reasoning = msg.get("reasoning_content") or ""
                    if reasoning.strip():
                        content = reasoning
                    else:
                        self._errors[model] = "模型返回空内容"
                        raise LLMUnavailableError(self._errors[model])
                return content
            self._errors[model] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            raise LLMUnavailableError(self._errors[model])

    async def chat(self, messages: List[Dict[str, str]], temperature: float = 0.7,
                   max_tokens: Optional[int] = None, json_mode: bool = False) -> str:
        """对话补全；自动探测可用模型后缓存"""
        if self.disabled:
            raise LLMUnavailableError("未配置 LLM_API_KEY")
        if self._quota_cooldown_until > time.time():
            raise LLMUnavailableError("LLM 限流/配额冷却中（约 20 秒后自动恢复）")
        max_tokens = max_tokens or self.max_tokens

        models = [self.active_model] if self.active_model else self.candidates
        last_err: Optional[Exception] = None
        for model in models:
            if not model:
                continue
            for attempt in (1, 2):
                try:
                    content = await self._chat_once(
                        model, messages, temperature, max_tokens, json_mode
                    )
                    if self.active_model != model:
                        logger.info(f"✅ LLM 模型探测成功: {model}")
                    self.active_model = model
                    # 调用成功：清除限流冷却（之前的 429 只是瞬时抖动）
                    self._quota_cooldown_until = 0.0
                    return content
                except Exception as e:  # noqa: BLE001
                    last_err = e
                    msg = str(e) or type(e).__name__
                    logger.warning(f"⚠️ LLM 模型 {model} 调用失败（第{attempt}次）: {msg}")
                    if attempt == 1 and _is_retryable(msg):
                        # 瞬时错误（限流/超时等）：退避后重试同一模型
                        await asyncio.sleep(8)
                        continue
                    break
        # 全部候选模型都失败：若为限流/配额类错误，进入短冷却，让后续调用快速失败而不是逐个空转
        if _is_quota_error(str(last_err) if last_err else ""):
            self._quota_cooldown_until = time.time() + 20
        raise LLMUnavailableError(f"所有候选模型均不可用: {last_err or type(last_err).__name__}")

    async def chat_json(self, messages: List[Dict[str, str]],
                        temperature: float = 0.3) -> Dict[str, Any]:
        """对话补全并解析 JSON（容忍 markdown 代码块包裹；失败时降级重试）"""
        content = await self.chat(messages, temperature=temperature, json_mode=True)
        try:
            return self.extract_json(content)
        except Exception:
            # 兜底：json_mode 下偶发空/异常输出时，去掉 json_mode 从正文中提取
            content = await self.chat(messages, temperature=temperature, json_mode=False)
            return self.extract_json(content)

    @staticmethod
    def extract_json(content: str) -> Dict[str, Any]:
        text = content.strip()
        fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
        if fence:
            text = fence.group(1).strip()
        try:
            import json
            return json.loads(text)
        except Exception:
            # 兜底：截取第一个 { 到最后一个 }
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                import json
                return json.loads(text[start:end + 1])
            raise


_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端（单例）"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
