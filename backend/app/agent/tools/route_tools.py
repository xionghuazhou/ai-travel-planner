"""路线规划工具（最近邻贪心算法 + Haversine 球面距离）"""
import logging
import math
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RouteOptimizer:
    """路线优化工具"""

    async def optimize(
        self,
        spots: List[Dict[str, Any]],
        start_location: Optional[str] = None,
        optimization_goal: str = "time",  # time / distance / balanced
    ) -> Dict[str, Any]:
        """
        优化景点游览路线（最近邻算法，生产环境可替换高德/百度 API）

        Args:
            spots: 景点列表，包含 id/name, lat, lng, duration
        """
        logger.info(f"🗺️ 优化路线，共 {len(spots)} 个景点")
        if not spots:
            return {"optimized_order": [], "total_distance_km": 0,
                    "estimated_time_minutes": 0, "segments": []}
        if len(spots) <= 2:
            return {
                "optimized_order": [s.get("id") or s.get("name") for s in spots],
                "total_distance_km": 0,
                "estimated_time_minutes": sum(s.get("duration", 120) for s in spots),
                "segments": [],
            }

        n = len(spots)
        distance_matrix = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    distance_matrix[i][j] = self._haversine(
                        spots[i].get("lat") or 0, spots[i].get("lng") or 0,
                        spots[j].get("lat") or 0, spots[j].get("lng") or 0,
                    )

        # 最近邻贪心
        visited = [False] * n
        route = []
        current = 0
        visited[current] = True
        route.append(current)
        for _ in range(n - 1):
            nearest, min_dist = -1, float("inf")
            for j in range(n):
                if not visited[j] and distance_matrix[current][j] < min_dist:
                    nearest, min_dist = j, distance_matrix[current][j]
            if nearest != -1:
                route.append(nearest)
                visited[nearest] = True
                current = nearest

        total_distance = sum(
            distance_matrix[route[i]][route[i + 1]] for i in range(len(route) - 1)
        )
        total_time = sum(s.get("duration", 120) for s in spots)
        # 假设平均移动速度 30km/h，每段加 15 分钟缓冲
        travel_time = (total_distance / 30) * 60 + (len(route) - 1) * 15

        return {
            "optimized_order": [spots[i].get("id") or spots[i].get("name") for i in route],
            "total_distance_km": round(total_distance, 2),
            "estimated_time_minutes": int(total_time + travel_time),
            "segments": [
                {
                    "from": spots[route[i]].get("name") or spots[route[i]].get("id"),
                    "to": spots[route[i + 1]].get("name") or spots[route[i + 1]].get("id"),
                    "distance_km": round(distance_matrix[route[i]][route[i + 1]], 2),
                    "estimated_time_min": int(
                        (distance_matrix[route[i]][route[i + 1]] / 30) * 60 + 15
                    ),
                }
                for i in range(len(route) - 1)
            ],
        }

    def _haversine(self, lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """计算两点之间的球面距离（km）"""
        if not any([lat1, lng1, lat2, lng2]):
            return 0.0
        R = 6371
        lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
