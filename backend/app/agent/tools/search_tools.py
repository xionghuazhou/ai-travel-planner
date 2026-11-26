"""联网搜索工具（免密钥：必应中国 + DuckDuckGo 双后端自动切换）"""
import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import quote, unquote, urlparse, parse_qs

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", text or "")).strip()


async def _search_bing_cn(query: str, max_results: int) -> List[Dict[str, Any]]:
    """必应中国网页搜索（HTML 解析，免密钥）"""
    out = []
    async with httpx.AsyncClient(timeout=settings.SEARCH_TIMEOUT,
                                 follow_redirects=True, headers={"User-Agent": _UA}) as client:
        resp = await client.get(
            "https://cn.bing.com/search",
            params={"q": query, "count": str(max_results), "mkt": "zh-CN"},
        )
        resp.raise_for_status()
        html = resp.text
    blocks = re.findall(r'<li class="b_algo".*?</li>', html, re.S)
    for b in blocks[:max_results]:
        m = re.search(r'<h2[^>]*><a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', b, re.S)
        if not m:
            continue
        url, title = m.group(1), _clean(m.group(2))
        snip = ""
        ms = re.search(r'<p[^>]*>(.*?)</p>', b, re.S)
        if ms:
            snip = _clean(ms.group(1))
        if url.startswith("http"):
            out.append({"title": title, "snippet": snip, "url": url, "source": "bing"})
    return out


def _decode_ddg(url: str) -> str:
    """还原 DuckDuckGo 的跳转链接"""
    if "uddg=" in url:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
    return url


async def _search_duckduckgo(query: str, max_results: int) -> List[Dict[str, Any]]:
    """DuckDuckGo HTML 版搜索（免密钥）"""
    out = []
    async with httpx.AsyncClient(timeout=settings.SEARCH_TIMEOUT,
                                 follow_redirects=True, headers={"User-Agent": _UA}) as client:
        resp = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
        )
        resp.raise_for_status()
        html = resp.text
    blocks = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', html, re.S)
    snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    for i, (url, title) in enumerate(blocks[:max_results]):
        real = _decode_ddg(url)
        snip = _clean(snippets[i]) if i < len(snippets) else ""
        if real.startswith("http"):
            out.append({"title": _clean(title), "snippet": snip, "url": real, "source": "duckduckgo"})
    return out


class WebSearchTool:
    """联网搜索工具：为 Agent 提供最新的旅行资讯"""

    name = "web_search"
    description = (
        "联网搜索最新旅行信息（开放时间、票价变动、临时活动、注意事项等）。"
        "输入：搜索关键词"
    )

    async def search(self, query: str, max_results: int = 6) -> List[Dict[str, Any]]:
        """执行搜索，后端按配置自动切换"""
        backend = settings.SEARCH_BACKEND
        errors = []
        order = {
            "auto": [_search_bing_cn, _search_duckduckgo],
            "bing_cn": [_search_bing_cn],
            "duckduckgo": [_search_duckduckgo],
        }.get(backend, [_search_bing_cn, _search_duckduckgo])
        for fn in order:
            try:
                results = await fn(query, max_results)
                if results:
                    logger.info(f"🌐 联网搜索成功（{fn.__name__}）：{len(results)} 条结果")
                    return results
                errors.append(f"{fn.__name__}: 无结果")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"搜索后端 {fn.__name__} 失败: {e}")
                errors.append(f"{fn.__name__}: {e}")
        logger.warning(f"⚠️ 联网搜索不可用: {errors}")
        return []

    async def run(self, query: str) -> str:
        results = await self.search(query, max_results=6)
        if not results:
            return f"暂时无法联网搜索「{query}」的结果。"
        lines = [f"**「{query}」联网搜索结果：**\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r['title']}**\n   {r['snippet']}\n   来源: {r['url']}\n")
        return "\n".join(lines)
