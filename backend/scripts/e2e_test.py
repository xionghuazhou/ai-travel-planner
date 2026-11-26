"""端到端验证脚本：健康检查 → 注册 → 景点 → Agent 对话 → 行程保存"""
import json
import sys

import httpx

BASE = "http://localhost:8000"


def main():
    ok = True

    # 1. 健康检查
    r = httpx.get(f"{BASE}/health", timeout=10).json()
    print(f"[1] 健康检查: status={r['status']}, llm={r['llm']}")
    if r["status"] != "ok":
        ok = False

    # 2. 注册/登录
    username = "tester01"
    r = httpx.post(f"{BASE}/api/v1/auth/register", timeout=15, json={
        "username": username, "email": f"{username}@test.com", "password": "test123456"})
    if r.status_code != 200:
        rr = httpx.post(f"{BASE}/api/v1/auth/login", timeout=15,
                        json={"username": username, "password": "test123456"})
        token = rr.json()["access_token"]
    else:
        token = r.json()["access_token"]
    print(f"[2] 认证: token={token[:20]}...")
    headers = {"Authorization": f"Bearer {token}"}

    # 3. 景点种子
    spots = httpx.get(f"{BASE}/api/v1/spots", params={"limit": 3}, timeout=15).json()
    print(f"[3] 景点知识库: {len(spots)} 条示例 -> {[s['name'] for s in spots]}")
    if not spots:
        ok = False

    # 4. Agent 对话（完整规划流程）
    print("[4] Agent 对话中（联网搜索+思考，约 10-60 秒）…")
    r = httpx.post(f"{BASE}/api/v1/agent/chat", timeout=300, headers=headers, json={
        "message": "我想去日本东京，4月初，5天2人，预算2万，喜欢文化"})
    if r.status_code != 200:
        print(f"    ✗ 对话失败: {r.status_code} {r.text[:300]}")
        ok = False
    else:
        data = r.json()
        print(f"    意图: {data['intent']}, 模式: {data['mode']}, "
              f"思考步骤: {len(data['thinking_steps'])}, 联网来源: {len(data['web_sources'])}")
        for s in data["thinking_steps"]:
            print(f"      - [{s['node']}] {s['message'][:70]}")
        days = data["itinerary"]["days"] if data["itinerary"] else []
        print(f"    行程: {len(days)} 天, "
              f"景点总数: {sum(len(d['spots']) for d in days)}")
        print(f"    回复预览: {data['message'][:150]}...")

        # 5. 保存行程
        if days:
            tr = httpx.post(f"{BASE}/api/v1/trips", timeout=30, headers=headers, json={
                "title": "东京5日AI之旅", "destination": "东京",
                "start_date": days[0].get("date") or "2026-04-01",
                "end_date": days[-1].get("date") or "2026-04-05",
                "budget": 20000, "travelers": 2, "days": days})
            print(f"[5] 保存行程: HTTP {tr.status_code} -> {tr.json().get('title') if tr.status_code == 200 else tr.text[:200]}")
            if tr.status_code == 200:
                tid = tr.json()["id"]
                d = httpx.get(f"{BASE}/api/v1/trips/{tid}", timeout=15, headers=headers).json()
                print(f"    行程详情: {len(d['days'])} 天, "
                      f"首日景点: {[s['name'] for s in d['days'][0]['spots']][:3]}")

    print("\n" + ("✅ 端到端验证通过" if ok else "❌ 存在失败项"))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
