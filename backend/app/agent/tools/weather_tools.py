"""天气查询工具（真实 API 优先，模拟数据兜底）"""
import logging
import random
from datetime import date, timedelta
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class WeatherTool:
    """天气查询工具"""

    async def get_weather(
        self,
        city: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """获取天气预报"""
        # 兼容 LLM 解析出的字符串日期
        def _to_date(v):
            if v is None or isinstance(v, date):
                return v
            if isinstance(v, str):
                try:
                    return date.fromisoformat(v[:10])
                except ValueError:
                    return None
            return None

        start_date = _to_date(start_date)
        end_date = _to_date(end_date)
        logger.info(f"🌤️ 查询 {city} 天气")
        if settings.WEATHER_API_KEY:
            try:
                return await self._fetch_from_api(city, start_date, end_date)
            except Exception as e:  # noqa: BLE001
                logger.warning(f"天气 API 调用失败: {e}，使用模拟数据")
        return self._get_mock_weather(city, start_date, end_date)

    async def _fetch_from_api(
        self, city: str, start_date: Optional[date], end_date: Optional[date]
    ) -> Dict[str, Any]:
        """从真实 API 获取天气（Open-Meteo 免费接口，无 Key 也可用）"""
        geo = await self._geocode(city)
        lat, lng = geo["lat"], geo["lng"]
        base = start_date or date.today()
        days = 7 if not end_date else max(1, (end_date - base).days + 1)
        days = min(days, 14)
        url = "https://api.open-meteo.com/v1/forecast"
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                url,
                params={
                    "latitude": lat,
                    "longitude": lng,
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                    "timezone": "auto",
                    "forecast_days": days,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        daily = data.get("daily", {})
        code_map = {0: ("晴", "☀️"), 1: ("多云", "⛅"), 2: ("多云", "⛅"), 3: ("阴", "☁️"),
                    45: ("雾", "🌫️"), 51: ("小雨", "🌦️"), 61: ("小雨", "🌧️"),
                    63: ("中雨", "🌧️"), 65: ("大雨", "⛈️"), 80: ("阵雨", "🌦️")}
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        forecasts = []
        for i, d in enumerate(daily.get("time", [])):
            code = daily.get("weather_code", [])[i] if i < len(daily.get("weather_code", [])) else 1
            wtype, icon = code_map.get(code, ("多云", "⛅"))
            forecasts.append({
                "date": d,
                "weekday": weekdays[(base + timedelta(days=i)).weekday()],
                "weather": wtype,
                "icon": icon,
                "temp_high": round(daily["temperature_2m_max"][i]),
                "temp_low": round(daily["temperature_2m_min"][i]),
            })
        return {"city": city, "forecasts": forecasts,
                "tips": self._generate_weather_tips(forecasts)}

    async def _geocode(self, city: str) -> Dict[str, float]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": city, "count": 1, "language": "zh"},
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])
            if not results:
                return {"lat": 39.9, "lng": 116.4}
            r = results[0]
            return {"lat": r["latitude"], "lng": r["longitude"]}

    def _get_mock_weather(
        self, city: str, start_date: Optional[date], end_date: Optional[date]
    ) -> Dict[str, Any]:
        """生成模拟天气数据（用于离线/测试）"""
        weather_types = [
            {"type": "晴", "icon": "☀️", "temp_range": (18, 28)},
            {"type": "多云", "icon": "⛅", "temp_range": (16, 25)},
            {"type": "阴", "icon": "☁️", "temp_range": (14, 22)},
            {"type": "小雨", "icon": "🌧️", "temp_range": (15, 23)},
        ]
        forecasts = []
        base_date = start_date or date.today()
        num_days = 7 if not end_date else max(1, (end_date - base_date).days + 1)
        weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i in range(min(num_days, 14)):
            weather = random.choice(weather_types)
            day = base_date + timedelta(days=i)
            forecasts.append({
                "date": day.isoformat(),
                "weekday": weekdays[day.weekday()],
                "weather": weather["type"],
                "icon": weather["icon"],
                "temp_high": weather["temp_range"][1] + random.randint(-2, 2),
                "temp_low": weather["temp_range"][0] + random.randint(-2, 2),
                "wind": f"{random.randint(1, 3)}级",
            })
        return {"city": city, "forecasts": forecasts,
                "tips": self._generate_weather_tips(forecasts)}

    def _generate_weather_tips(self, forecasts: list) -> str:
        """根据天气预报生成出行建议"""
        tips = []
        rainy_days = [f for f in forecasts if "雨" in f.get("weather", "")]
        if rainy_days:
            tips.append(f"行程中有 {len(rainy_days)} 天可能有雨，建议携带雨具。")
        temps = [f["temp_high"] for f in forecasts] + [f["temp_low"] for f in forecasts]
        if temps:
            avg_high = sum(temps) / len(temps)
            if avg_high > 30:
                tips.append("气温较高，注意防暑防晒，多补充水分。")
            elif avg_high < 15:
                tips.append("气温较低，建议携带外套和保暖衣物。")
        return " ".join(tips) if tips else "天气总体良好，适合出行。"
