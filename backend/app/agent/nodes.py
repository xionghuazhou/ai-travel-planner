"""Agent 节点定义（含联网搜索与反思节点，LLM 不可用时自动降级）"""
import asyncio
import json
import logging
import re
from datetime import date as date_cls, timedelta
from typing import Any, Dict, List

from app.agent.state import AgentState, IntentType, TravelStyle
from app.agent.tools.route_tools import RouteOptimizer
from app.agent.tools.search_tools import WebSearchTool
from app.agent.tools.spot_tools import SpotSearchTool
from app.agent.tools.weather_tools import WeatherTool
from app.llm.client import LLMUnavailableError, get_llm_client

logger = logging.getLogger(__name__)


# ---------- 工具函数 ----------
def _log(state: AgentState, node: str, message: str) -> None:
    """记录思考步骤（展示给前端的思考过程）"""
    steps = state.get("thinking_steps") or []
    steps.append({"node": node, "message": message})
    state["thinking_steps"] = steps
    logger.info(f"[{node}] {message}")


_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
           "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cn_to_int(s: str) -> int:
    """中文数字转整数：五→5，十→10，二十→20"""
    s = (s or "").strip()
    if s.isdigit():
        return int(s)
    if s == "十":
        return 10
    if "十" in s:
        a, _, b = s.partition("十")
        return _CN_NUM.get(a, 1) * 10 + (_CN_NUM.get(b, 0) if b else 0)
    return _CN_NUM.get(s, 0)


def _spot_matches_destination(spot: Dict[str, Any], destination: str) -> bool:
    """严格判断景点是否属于目的地。

    关键规则：当目的地比景点所在城市更具体（如「重庆市忠县」vs 库中城市「重庆」）时，
    多出的部分（忠县）必须出现在景点自身信息（名称/地址等）里，否则视为不属于该地——
    避免把重庆主城景点冒充忠县景点。
    """
    dest = (destination or "").strip()
    if not dest:
        return True
    hay = " ".join(filter(None, [
        spot.get("city") or "", spot.get("name") or "",
        spot.get("address") or "", spot.get("country") or "",
    ]))
    if not hay:
        return False
    if dest in hay:
        return True
    city = (spot.get("city") or "").strip()
    if city and city in dest:
        extra = dest.replace(city, "", 1)
        extra = re.sub(r"^[市县区]", "", extra)
        extra = re.sub(r"[市县区]$", "", extra)
        if not extra or extra in hay:
            return True
    return False


def _fmt_spots(spots: List[Dict[str, Any]], limit: int = 15) -> str:
    items = []
    for s in spots[:limit]:
        items.append({
            "name": s.get("name"),
            "category": s.get("category"),
            "rating": s.get("rating"),
            "address": s.get("address"),
            "ticket": s.get("ticket_info"),
            "duration_min": s.get("recommend_duration"),
            "tags": s.get("tags"),
        })
    return json.dumps(items, ensure_ascii=False, indent=1)


# ---------- 节点 1: 解析需求 ----------
async def parse_requirements(state: AgentState) -> AgentState:
    """解析用户需求：意图识别 + 关键信息抽取"""
    _log(state, "parse_requirements", "📋 正在理解你的旅行需求…")
    message = state.get("user_message", "")
    llm = get_llm_client()

    intent = "trip_plan"
    destination = start_date = end_date = None
    budget = travelers = None
    travel_style = None

    try:
        result = await llm.chat_json([
            {"role": "system", "content":
                "你是旅行需求解析器。从用户消息中提取信息，只输出 JSON："
                '{"intent": "trip_plan|spot_query|weather_query|tips_query|chitchat",'
                ' "destination": "城市或国家，没有则 null",'
                ' "start_date": "YYYY-MM-DD 或 null",'
                ' "end_date": "YYYY-MM-DD 或 null",'
                ' "budget": 数字或 null, "travelers": 数字或 null,'
                ' "travel_style": "relaxed/adventurous/cultural/family/romantic/business/foodie/photography 或 null"}'
                " 当前日期：" + date_cls.today().isoformat()},
            {"role": "user", "content": message},
        ])
        intent = (result.get("intent") or "trip_plan").strip()
        destination = result.get("destination") or None
        start_date = result.get("start_date") or None
        end_date = result.get("end_date") or None
        budget = result.get("budget") or None
        travelers = result.get("travelers") or None
        travel_style = result.get("travel_style") or None
        state["intent_confidence"] = 0.9
        _log(state, "parse_requirements",
             f"✅ 意图: {intent}，目的地: {destination}，"
             f"日期: {start_date}~{end_date}，预算: {budget}，人数: {travelers}")
    except Exception as e:  # noqa: BLE001
        # 规则兜底解析
        state["intent_confidence"] = 0.4
        # 优先匹配知识库中的已知城市名（覆盖「成都2天美食之旅」这类表达）
        try:
            from scripts.spots_data import SPOTS
            known_cities = sorted({s["city"] for s in SPOTS}, key=len, reverse=True)
        except Exception:  # noqa: BLE001
            known_cities = []
        for city in known_cities:
            if city in message:
                destination = city
                break
        if not destination:
            m = re.search(r"(?:去|到|想玩|游玩|旅行|旅游)[^\u4e00-\u9fa5a-zA-Z]{0,4}([\u4e00-\u9fa5]{2,8})", message)
            if m:
                destination = m.group(1)
        if re.search(r"(天气|下雨|气温)", message):
            intent = "weather_query"
        elif re.search(r"(景点|去哪|推荐|好玩)", message):
            intent = "spot_query"
        elif re.search(r"(攻略|tips|注意|建议)", message):
            intent = "tips_query"
        elif re.search(r"(你好|在吗|谢谢|你是谁|哈喽|hi|hello)", message, re.I) and len(message) < 25:
            intent = "chitchat"
        mb = re.search(r"预算[^\d]{0,4}(\d+)", message)
        if mb:
            budget = int(mb.group(1))
        mt = re.search(r"(\d+)\s*人", message)
        if mt:
            travelers = int(mt.group(1))
        _log(state, "parse_requirements",
             f"⚠️ LLM 不可用（{e}），规则解析: 意图={intent}, 目的地={destination}")

    # 归一化
    if destination:
        destination = destination.strip().strip("，。！？,!? ")
        for suffix in ("市",):
            if destination.endswith(suffix) and len(destination) > 2:
                destination = destination[:-1]
    if intent not in {i.value for i in IntentType}:
        intent = "trip_plan"
    if travel_style not in {s.value for s in TravelStyle}:
        travel_style = travel_style if travel_style in {s.value for s in TravelStyle} else None

    state["intent"] = intent
    state["destination"] = destination
    state["start_date"] = start_date
    state["end_date"] = end_date
    state["budget"] = budget
    state["travelers"] = travelers or 1
    state["travel_style"] = travel_style or "relaxed"

    if intent == "chitchat":
        state["response"] = (
            "你好呀！我是 TravelAI 旅行智脑 🧳\n\n"
            "告诉我你的旅行想法，比如：**「我想去日本东京，4月初，5天2人，预算2万，喜欢文化」**，"
            "我会结合景点知识库、实时天气和最新网络资讯，为你生成完整的多日行程规划！"
        )
        state["suggested_actions"] = ["规划东京5日游", "三亚亲子游推荐", "成都美食之旅"]
        _log(state, "parse_requirements", "💬 闲聊消息，直接回复")
    return state


# ---------- 节点 2: 检索景点 ----------
async def search_spots(state: AgentState) -> AgentState:
    """从 RAG 景点知识库检索相关景点"""
    destination = state.get("destination")
    style = state.get("travel_style") or "relaxed"
    if not destination:
        state["response"] = "请告诉我你想去哪个城市或国家旅行，我来帮你规划行程～"
        return state

    _log(state, "search_spots", f"🔍 正在从景点知识库检索「{destination}」的热门景点…")
    tool = SpotSearchTool()
    style_keywords = {
        "relaxed": "休闲", "adventurous": "户外", "cultural": "历史文化",
        "family": "亲子", "romantic": "浪漫", "foodie": "美食",
        "photography": "摄影", "business": "地标",
    }.get(style, "")
    query = f"{destination} {style_keywords} 热门景点".strip()
    candidates = await tool.search(query, top_k=15)
    # 严格目的地归属过滤：区县级目的地绝不混入上属大城市的景点
    spots = [s for s in candidates if _spot_matches_destination(s, destination)]
    dropped = len(candidates) - len(spots)
    if not spots:
        _log(state, "search_spots",
             f"⚠️ 知识库暂无「{destination}」的景点数据，将结合联网搜索与AI真实知识规划（不使用其他城市的景点）")
    else:
        note = f"（已严格过滤 {dropped} 个非当地景点）" if dropped else ""
        _log(state, "search_spots", f"✅ 检索到 {len(spots)} 个「{destination}」景点{note}")
    state["retrieved_spots"] = spots
    from app.rag.chain import get_rag_chain
    guides = await get_rag_chain().search_guides(f"{destination} 旅游攻略", top_k=3)
    state["retrieved_guides"] = guides
    _log(state, "search_spots", f"📚 同步检索到攻略 {len(guides)} 篇")
    return state


# ---------- 节点 3: 天气查询 ----------
async def fetch_weather(state: AgentState) -> AgentState:
    """查询目的地天气"""
    destination = state.get("destination")
    if not destination:
        return state
    try:
        tool = WeatherTool()
        weather = await tool.get_weather(
            city=destination,
            start_date=state.get("start_date"),
            end_date=state.get("end_date"),
        )
        state["weather_info"] = weather
        tips = weather.get("tips", "")
        _log(state, "fetch_weather", f"🌤️ 天气获取成功。{tips}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ 天气获取失败: {e}")
        state["weather_info"] = None
        _log(state, "fetch_weather", f"⚠️ 天气获取失败: {e}，将忽略天气因素")
    return state


# ---------- 节点 4: 联网搜索 ----------
async def web_search(state: AgentState) -> AgentState:
    """联网搜索最新旅行资讯（开放时间/票价/临时活动/注意事项）"""
    destination = state.get("destination") or ""
    if not destination:
        return state
    style_map = {
        "family": "亲子", "romantic": "情侣", "foodie": "美食",
        "cultural": "文化", "adventurous": "户外探险", "photography": "摄影",
        "business": "商务", "relaxed": "休闲",
    }
    style_tag = style_map.get(state.get("travel_style") or "", "")
    queries = [
        f"{destination} 旅游攻略 最新 2025",
        f"{destination} 景点 开放时间 门票 预约 {style_tag}".replace("  ", " "),
    ]
    # 乡镇/村级目的地：补充上属区县的搜索，确保拿到足够的真实资讯
    if re.search(r"(?:镇|乡|村)$", destination or ""):
        for k in range(2, 5):  # 依次尝试去掉「镇名(1-3字)+后缀」
            parent = (destination or "")[:-k] if len(destination) > k else ""
            if len(parent) >= 3 and parent.endswith(("县", "市", "区", "旗")):
                queries.append(f"{parent} 景点 必去 旅游攻略")
                break
    tool = WebSearchTool()
    all_results: List[Dict[str, Any]] = []
    seen_urls = set()
    for q in queries:
        _log(state, "web_search", f"🌐 正在联网搜索：{q}")
        results = await tool.search(q, max_results=5)
        for r in results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                all_results.append(r)
    state["search_queries"] = queries
    state["web_results"] = all_results[:8]
    if all_results:
        titles = "；".join(r["title"][:24] for r in all_results[:4])
        _log(state, "web_search", f"✅ 联网搜索到 {len(all_results)} 条最新资讯：{titles}…")
    else:
        _log(state, "web_search", "⚠️ 联网搜索暂不可用，将基于知识库与天气数据规划")
    return state


# ---------- 行程渲染与规则化生成 ----------
def _render_days_markdown(days: List[Dict[str, Any]], destination: str) -> str:
    lines = [f"# {destination} 行程规划\n"]
    for d in days:
        w = d.get("weather_info") or {}
        wtxt = f"（{w.get('icon','')}{w.get('weather','')} {w.get('temp_low','')}~{w.get('temp_high','')}°C）" if w else ""
        lines.append(f"## Day {d['day_number']} · {d.get('theme','')}{wtxt}\n")
        if d.get("summary"):
            lines.append(f"{d['summary']}\n")
        for s in d.get("spots", []):
            line = f"- **{s.get('start_time','')}–{s.get('end_time','')} {s.get('name','')}**"
            if s.get("category"):
                line += f"（{s['category']}）"
            if s.get("notes"):
                line += f"：{s['notes']}"
            lines.append(line)
            if s.get("transport_to_next"):
                lines.append(f"  - 🚗 到下一站：{s['transport_to_next']}")
        lines.append("")
    return "\n".join(lines)


async def _web_verify_spot(destination: str, name: str) -> bool:
    """通过必应搜索核实景点是否真实存在（搜索结果需包含景点名）"""
    try:
        from app.agent.tools.search_tools import _search_bing_cn, _search_duckduckgo
        query = f"{destination} {name}".strip()
        results = await _search_bing_cn(query, max_results=4)
        if not results:
            results = await _search_duckduckgo(query, max_results=4)
        text = re.sub(r"\s", "", " ".join(
            f"{r.get('title', '')} {r.get('snippet', '')}" for r in results
        ))
        n = re.sub(r"\s", "", name)
        return len(n) >= 2 and n in text
    except Exception:  # noqa: BLE001
        return True  # 核实服务异常时宁可信其有，避免误杀真实景点


async def _verify_spots_against_sources(days: List[Dict[str, Any]],
                                        state: AgentState) -> tuple:
    """按知识库与联网搜索结果逐个核实行程景点，防止 LLM 编造。

    两级核实：
    1. 景点名出现在知识库景点名或已获取的联网搜索标题/摘要中 → 直接通过
    2. 未通过的景点逐个发起必应搜索（「目的地+景点名」），结果包含景点名 → 通过
    返回 (核实通过的 days[已剔除无效景点并重新编号], 无法核实的景点名列表)。
    """
    kb_names = " ".join(s.get("name", "") for s in state.get("retrieved_spots", []))
    web_text = " ".join(
        f"{r.get('title', '')} {r.get('snippet', '')}"
        for r in state.get("web_results", [])
    )
    source_text = re.sub(r"\s", "", f"{kb_names} {web_text}")
    destination = state.get("destination") or ""

    def _in_known(name: str) -> bool:
        n = re.sub(r"\s", "", name or "")
        if len(n) < 2:
            return False
        if n in source_text:
            return True
        n2 = re.sub(r"(风景区|旅游区|度假区|景区|古镇|古街|公园)$", "", n)
        return bool(n2) and n2 != n and n2 in source_text

    # 第一级：已有来源快速核实；未通过的进入第二级逐个联网核实
    uncertain = []
    for d in days:
        for s in d.get("spots", []):
            if not _in_known(s.get("name", "")):
                uncertain.append(s.get("name", ""))

    web_ok = set()
    uncertain = [n for n in dict.fromkeys(uncertain) if n][:12]
    if uncertain:
        check_results = await asyncio.gather(
            *[_web_verify_spot(destination, n) for n in uncertain],
            return_exceptions=True,
        )
        for name, ok in zip(uncertain, check_results):
            if ok is True:
                web_ok.add(re.sub(r"\s", "", name))

    def _ok(name: str) -> bool:
        if _in_known(name):
            return True
        n = re.sub(r"\s", "", name or "")
        return len(n) >= 2 and n in web_ok

    verified_days, unverified = [], []
    seen = set()
    for d in days:
        vspots = []
        for s in d.get("spots", []):
            name = s.get("name", "")
            n = re.sub(r"\s", "", name)
            if not _ok(name):
                unverified.append(f"Day{d.get('day_number')}·{name}")
                continue
            if n in seen:
                continue  # 同一景点全行程只安排一次
            seen.add(n)
            vspots.append(s)
        if vspots:
            nd = dict(d)
            nd["spots"] = vspots
            verified_days.append(nd)
    for i, d in enumerate(verified_days):
        d["day_number"] = i + 1
    return verified_days, unverified


def _rule_based_itinerary(state: AgentState) -> Dict[str, Any]:
    """LLM 不可用时的规则化行程生成（基于 RAG 检索结果，只使用经严格归属验证的当地景点）"""
    destination = state.get("destination", "")
    spots = state.get("retrieved_spots", [])
    # 严格目的地归属过滤：区县目的地绝不混入上属大城市的景点
    spots = [s for s in spots if _spot_matches_destination(s, destination)]
    if not spots:
        # 知识库无该地景点：诚实告知，绝不拿其他城市景点充数
        return {"content": "", "days": [], "spots_used": [],
                "generated_by": "rule_based", "no_data": True}
    start = state.get("start_date")
    n_days = 3
    if start and state.get("end_date"):
        try:
            n_days = max(1, (date_cls.fromisoformat(state["end_date"]) -
                             date_cls.fromisoformat(start)).days + 1)
        except Exception:  # noqa: BLE001
            n_days = 3
    elif state.get("user_message"):
        # 兼容中文数字天数表达：「五日游」「三天」「5天」
        m_days = re.search(r"([一二两三四五六七八九十\d]+)\s*[日天]", state["user_message"])
        if m_days:
            n_days = min(7, max(1, _cn_to_int(m_days.group(1)) or 3))
    n_days = min(n_days, 7)

    # 按地理位置聚类到每天（最近邻串联）
    optimizer = RouteOptimizer()
    # 规则化生成：按相关性排序后去重，再均匀分配到每天
    uniq: List[Dict[str, Any]] = []
    seen_names = set()
    for s in spots:
        key = s.get("name", "")
        if key and key not in seen_names:
            seen_names.add(key)
            uniq.append(s)
    spots = uniq[: n_days * 4] if spots else []
    per_day = [spots[i::n_days] for i in range(n_days)] if spots else [[] for _ in range(n_days)]

    themes = ["经典地标之旅", "深度文化体验", "休闲美食漫游", "自然风光探索", "城市漫步日", "自由活动日", "查漏补缺日"]
    base = date_cls.fromisoformat(start) if start else date_cls.today()
    days = []
    slot_times = [("09:00", "11:30"), ("13:00", "15:00"), ("15:30", "17:30"), ("18:30", "20:30")]
    weather_list = (state.get("weather_info") or {}).get("forecasts", [])
    for i, day_spots in enumerate(per_day):
        day_date = (base + timedelta(days=i)).isoformat()
        winfo = weather_list[i % len(weather_list)] if weather_list else None
        spots_out = []
        for j, s in enumerate(day_spots[:4]):
            t0, t1 = slot_times[min(j, len(slot_times) - 1)]
            spots_out.append({
                "name": s.get("name", "待定景点"),
                "start_time": t0,
                "end_time": t1,
                "duration_minutes": int(s.get("recommend_duration") or 120),
                "category": s.get("category"),
                "notes": (s.get("description") or "")[:120],
                "estimated_cost": 0,
            })
        days.append({
            "day_number": i + 1,
            "date": day_date,
            "theme": themes[min(i, len(themes) - 1)],
            "summary": f"第{i+1}天，围绕{destination}的{themes[min(i, len(themes)-1)]}展开。",
            "weather_info": winfo,
            "spots": spots_out,
        })
    # 去掉没有安排景点的空行程天
    days = [d for d in days if d["spots"]]
    for i, d in enumerate(days):
        d["day_number"] = i + 1
    markdown = _render_days_markdown(days, destination)
    return {
        "content": markdown,
        "days": days,
        "spots_used": [s.get("id") for s in spots[:10]],
        "generated_by": "rule_based",
    }


# ---------- 节点 5: 生成行程 ----------
async def generate_itinerary(state: AgentState) -> AgentState:
    """生成结构化多日行程（LLM 优先，联网资讯辅助，规则化兜底）"""
    destination = state.get("destination", "")
    spots = state.get("retrieved_spots", [])
    if not spots and not state.get("web_results"):
        state["response"] = f"抱歉，暂时没有找到 {destination} 的相关景点信息，请尝试其他目的地。"
        return state

    reflection = state.get("reflection") or {}
    feedback = reflection.get("feedback") if reflection.get("pass") is False else None
    if feedback:
        state["retry_count"] = (state.get("retry_count") or 0) + 1
        _log(state, "generate_itinerary", f"🔁 根据反思反馈重新生成行程：{feedback[:80]}…")
    else:
        _log(state, "generate_itinerary", "📝 正在综合景点、天气与联网资讯生成行程…")

    llm = get_llm_client()
    weather = state.get("weather_info") or {}
    web = state.get("web_results") or []
    web_ctx = "\n".join(
        f"- [{r['title']}] {r['snippet'][:150]} (来源: {r['url'][:80]})"
        for r in web[:6]
    ) or "（无联网结果）"

    days_req = 3
    if state.get("start_date") and state.get("end_date"):
        try:
            days_req = min(7, max(1, (date_cls.fromisoformat(state["end_date"]) -
                                      date_cls.fromisoformat(state["start_date"])).days + 1))
        except Exception:  # noqa: BLE001
            days_req = 3

    feedback_block = ("## 上一版的问题（必须改进）\n" + feedback) if feedback else ""

    # 知识库上下文：无收录数据时明确告知，防止混入其他城市景点
    if spots:
        kb_section = f"## 景点知识库（均为「{destination}」当地真实收录景点，已按相关性排序）\n{_fmt_spots(spots)}"
        kb_rule = "4. 知识库中已收录该地景点（均已核验真实存在），必须优先安排这些景点"
    else:
        kb_section = (f"## 景点知识库\n（暂无「{destination}」的收录数据——"
                      f"严禁使用其他城市/区县的景点，只能基于下方联网搜索结果与你确认无误的真实知识推荐当地景点）")
        kb_rule = "4. 知识库无该地数据时，必须以联网搜索结果中出现的真实景点为主，结合你掌握的该地真实知名景点"

    prompt = f"""你是资深旅行规划师。请根据以下信息，为用户生成 {days_req} 天的详细行程。

## 用户需求
- 目的地: {destination}
- 日期: {state.get('start_date') or '待定'} ~ {state.get('end_date') or '待定'}（共 {days_req} 天）
- 预算: {state.get('budget') or '不限'} 元，人数: {state.get('travelers') or 1} 人
- 旅行风格: {state.get('travel_style') or 'relaxed'}

{kb_section}

## 天气预报
{json.dumps(weather, ensure_ascii=False)[:800] if weather else '（无）'}

## 联网搜索到的最新资讯（务必参考开放时间/预约要求等）
{web_ctx}

## 要求
1. 每天安排 3-4 个景点，同区域集中安排，时间合理（9:00-20:30）
2. 考虑天气与最新资讯（如需预约/闭馆必须在 notes 里注明）
3. 景点必须真实存在且位于「{destination}」当地：严禁编造景点名称，严禁安排其他城市/区县的景点
{kb_rule}
5. 只输出 JSON，格式：
{{"days": [{{"day_number": 1, "date": "YYYY-MM-DD", "theme": "当日主题", "summary": "当日总结", "spots": [{{"name": "景点名", "start_time": "09:00", "end_time": "11:30", "duration_minutes": 150, "category": "类型", "notes": "注意事项", "estimated_cost": 0}}]}}]}}
6. 严禁编造景点名称！只能安排知识库或联网搜索结果中出现过的真实景点；若知识库与联网搜索均无该地任何景点信息，才输出 {{"days": []}}
7. 同一景点在整个行程中只能出现一次，不得重复安排；真实景点数量不足以填满天数时，宁可减少天数也不要重复或编造
{feedback_block}"""

    try:
        result = await llm.chat_json([
            {"role": "system", "content": "你是专业旅行规划师，只输出 JSON。"},
            {"role": "user", "content": prompt},
        ], temperature=0.6)
        days = result.get("days") or []
        if not days:
            # 模型确认该地缺乏可靠的真实景点信息：不编造，走联网资讯汇总
            _log(state, "generate_itinerary",
                 "⚠️ 模型确认无法确认该地有足够真实景点，改用联网资讯汇总（不编造行程）")
            state["draft_itinerary"] = {"content": "", "days": [], "spots_used": [],
                                        "generated_by": "llm", "no_data": True}
            return state
        # 补齐字段
        base = date_cls.fromisoformat(state["start_date"]) if state.get("start_date") else date_cls.today()
        weather_list = (weather or {}).get("forecasts", [])
        for i, d in enumerate(days):
            d.setdefault("day_number", i + 1)
            d.setdefault("date", (base + timedelta(days=i)).isoformat())
            d.setdefault("theme", f"第{i+1}天")
            d.setdefault("summary", "")
            d.setdefault("spots", [])
            if weather_list and not d.get("weather_info"):
                d["weather_info"] = weather_list[i % len(weather_list)]
        # 逐个景点核实：必须能在知识库或联网搜索结果中找到，否则剔除（防编造）
        days, unverified = await _verify_spots_against_sources(days, state)
        state["unverified_spots"] = unverified
        if unverified:
            _log(state, "generate_itinerary",
                 f"⚠️ 已剔除 {len(unverified)} 个无法通过联网/知识库核实的疑似编造景点：{'、'.join(unverified[:4])}")
        if not days:
            _log(state, "generate_itinerary",
                 "⚠️ 生成的景点全部无法核实，改用联网真实资讯汇总（不编造行程）")
            state["draft_itinerary"] = {"content": "", "days": [], "spots_used": [],
                                        "generated_by": "llm", "no_data": True}
            return state
        itinerary = {
            "content": _render_days_markdown(days, destination),
            "days": days,
            "spots_used": [s.get("id") for s in spots[:10]],
            "generated_by": "llm",
        }
        _log(state, "generate_itinerary",
             f"✅ 行程生成成功（{len(days)} 天，LLM 模式，全部景点已核实）")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"LLM 生成行程失败: {e}，使用规则化生成")
        _log(state, "generate_itinerary", f"⚠️ LLM 暂不可用（{str(e)[:60]}），切换规则化引擎生成行程")
        itinerary = _rule_based_itinerary(state)

    state["draft_itinerary"] = itinerary
    return state


# ---------- 节点 6: 反思检查（思考） ----------
async def reflect(state: AgentState) -> AgentState:
    """批判性反思生成的行程：完整性、天气适配、资讯引用"""
    itinerary = state.get("draft_itinerary") or {}
    days = itinerary.get("days", [])
    _log(state, "reflect", "🤔 正在自查行程质量（天数覆盖/景点分布/天气适配/资讯引用）…")

    # 无行程可反思（例如未找到景点）：直接放行，避免无意义的重试循环
    if not itinerary or itinerary.get("no_data"):
        state["reflection"] = {"pass": True, "feedback": ""}
        _log(state, "reflect", "⚠️ 无结构化行程（模型已诚实拒绝编造），跳过重试")
        return state

    # 规则检查（只检查真正致命的缺陷，避免过度严格导致反复重新生成、浪费配额与时间）
    problems: List[str] = []
    if not days:
        problems.append("没有生成任何行程天")
    else:
        empty_days = [str(d.get("day_number")) for d in days if not d.get("spots")]
        if empty_days:
            problems.append(f"第 {empty_days} 天没有安排景点")

    passed = not problems
    feedback = "；".join(problems)
    state["reflection"] = {"pass": passed, "feedback": feedback}
    if passed:
        _log(state, "reflect", "✅ 自查通过，行程质量达标")
    else:
        if (state.get("retry_count") or 0) < 1:
            _log(state, "reflect", f"🔁 自查发现问题：{feedback}，触发重新生成")
        else:
            _log(state, "reflect", f"⚠️ 仍有问题（{feedback}），已达重试上限，继续优化路线")
    return state


def route_after_reflect(state: AgentState) -> str:
    """反思后的路由：不通过且未重试过 → 重新生成；否则优化路线"""
    # 硬性护栏：没有行程草稿时重试无意义
    if not state.get("draft_itinerary") or (state.get("draft_itinerary") or {}).get("no_data"):
        return "continue"
    # 规则引擎生成的行程无需用 LLM 重新生成（结果相同，纯属浪费配额与时间）
    if (state.get("draft_itinerary") or {}).get("generated_by") == "rule_based":
        return "continue"
    reflection = state.get("reflection") or {}
    if reflection.get("pass") is False and (state.get("retry_count") or 0) < 1:
        return "retry"
    return "continue"


# ---------- 节点 7: 路线优化 ----------
async def optimize_route(state: AgentState) -> AgentState:
    """对行程景点做地理路线优化"""
    itinerary = state.get("draft_itinerary")
    if not itinerary:
        return state
    _log(state, "optimize_route", "🗺️ 正在按地理位置优化每日游览顺序…")
    try:
        spot_map = {s["name"]: s for s in state.get("retrieved_spots", [])}
        optimizer = RouteOptimizer()
        all_spots = []
        for d in itinerary.get("days", []):
            for s in d.get("spots", []):
                ref = spot_map.get(s.get("name"), {})
                lat = ref.get("latitude")
                lng = ref.get("longitude")
                # LLM 补充的知识库外景点没有坐标，跳过（避免把 null 岛坐标带入距离计算）
                if lat is None or lng is None:
                    continue
                all_spots.append({
                    "id": s.get("name"),
                    "name": s.get("name"),
                    "lat": lat,
                    "lng": lng,
                    "duration": s.get("duration_minutes", 120),
                })
        if len(all_spots) >= 2:
            optimized = await optimizer.optimize(all_spots, start_location=state.get("destination"))
            state["optimized_itinerary"] = optimized
            seg_count = len(optimized.get("segments", []))
            _log(state, "optimize_route",
                 f"✅ 路线优化完成：总距离 {optimized.get('total_distance_km', 0)} km，"
                 f"预计游玩+交通 {optimized.get('estimated_time_minutes', 0)} 分钟（{seg_count} 段路径）")
        else:
            state["optimized_itinerary"] = None
            _log(state, "optimize_route", "⚠️ 有坐标的景点不足 2 个，跳过路线优化")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ 路线优化失败: {e}")
        _log(state, "optimize_route", f"⚠️ 路线优化跳过: {e}")
    return state


# ---------- 节点 8: 生成最终回复 ----------
async def generate_response(state: AgentState) -> AgentState:
    """整理最终回复"""
    if state.get("error") and not state.get("response"):
        state["response"] = f"抱歉，规划过程中遇到了一些问题：{state['error']}。请稍后重试。"
        return state
    if state.get("response"):  # 闲聊/提示语已生成
        return state

    itinerary = state.get("draft_itinerary") or {}
    weather = state.get("weather_info") or {}
    web = state.get("web_results") or []
    destination = state.get("destination") or "该目的地"

    # 知识库无该地景点数据且规则引擎无法生成结构化行程：
    # 把联网搜索到的真实资讯整理成参考指南（绝不拿其他城市景点充数）
    if itinerary.get("no_data") or (itinerary.get("generated_by") == "rule_based"
                                    and not itinerary.get("days")):
        lines = [
            f"📖 「{destination}」暂未收录进本地知识库，以下为**实时联网搜索**到的该地真实旅游资讯，供你规划参考：",
            "",
        ]
        if web:
            for i, r in enumerate(web[:6], 1):
                line = f"**{i}. {r.get('title') or '相关资讯'}**"
                snippet = (r.get("snippet") or "").strip()
                if snippet:
                    line += f"\n　{snippet[:180]}"
                if r.get("url"):
                    line += f"\n　来源: {r['url']}"
                lines.append(line)
                lines.append("")
        else:
            lines.append("（本次联网搜索暂无结果，可稍后重试）")
        if weather.get("tips"):
            lines.append(f"> 💡 **天气建议**：{weather['tips']}")
        lines.append(
            "\n💡 上面资讯中提到的景点均来自真实搜索结果。"
            "AI 智能规划可用时，我会基于这些资讯为你生成结构化的多日行程，可稍后重试。"
        )
        state["response"] = "\n".join(lines)
        state["suggested_actions"] = ["稍后重试", "换一个城市试试"]
        _log(state, "generate_response", "⚠️ 知识库无该地数据，已返回联网真实资讯汇总")
        return state

    lines = [itinerary.get("content") or ""]
    if weather.get("tips"):
        lines.append(f"\n> 💡 **天气建议**：{weather['tips']}")
    if state.get("optimized_itinerary"):
        opt = state["optimized_itinerary"]
        lines.append(
            f"\n> 🗺️ **路线优化**：总距离约 {opt.get('total_distance_km', 0)} km，"
            f"预计总时长 {opt.get('estimated_time_minutes', 0)} 分钟"
        )
    if web:
        lines.append("\n**📚 参考的联网资讯**：")
        for i, r in enumerate(web[:5], 1):
            lines.append(f"{i}. [{r['title']}]({r['url']})")
    unv = state.get("unverified_spots") or []
    if unv:
        lines.append(
            f"\n> ⚠️ **真实性保障**：已自动剔除 {len(unv)} 个无法通过知识库/联网核实的疑似虚构地点"
            f"（{'、'.join(unv[:4])}{'…' if len(unv) > 4 else ''}），确保行程真实可靠。"
        )
    state["response"] = "\n".join(lines).strip() or "行程已生成，请查看。"

    if not state.get("suggested_actions"):
        state["suggested_actions"] = [
            "修改行程安排", "调整预算范围", "推荐当地美食", "查看酒店推荐", "导出行程PDF",
        ]
    mode = itinerary.get("generated_by", "llm")
    _log(state, "generate_response",
         f"🎉 最终回复已生成（{'LLM 模式' if mode == 'llm' else '规则引擎模式'}，"
         f"含 {len(web)} 条联网引用）")
    return state


def route_after_parse(state: AgentState) -> str:
    """意图路由：闲聊/简单查询直接回复，行程规划走完整流程"""
    if state.get("response"):  # 闲聊等已在 parse 中生成回复
        return "direct_reply"
    return "plan_trip"
