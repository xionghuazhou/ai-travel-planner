<template>
  <div class="page-container">
    <a-card class="hero" :body-style="{ padding: '40px 36px' }">
      <h1 style="font-size: 30px; margin: 0 0 10px">🧳 TravelAI 旅行智脑</h1>
      <p style="color: #4e5969; font-size: 16px; margin: 0 0 26px">
        基于 LLM · Agent · RAG · LangGraph 的智能旅行规划系统 —— 用一句话，生成完整的多日行程
      </p>
      <a-space :size="14">
        <a-button type="primary" size="large" @click="$router.push('/chat')">
          🚀 开始 AI 行程规划
        </a-button>
        <a-button size="large" @click="$router.push('/trips')">查看我的行程</a-button>
      </a-space>
      <div class="features">
        <div class="feature">
          <div class="f-icon">🎯</div>
          <div class="f-title">智能行程规划</div>
          <div class="f-desc">基于偏好和预算自动生成最优路线</div>
        </div>
        <div class="feature">
          <div class="f-icon">🤖</div>
          <div class="f-title">多阶段思考</div>
          <div class="f-desc">LangGraph 工作流：解析→检索→天气→生成→反思→优化</div>
        </div>
        <div class="feature">
          <div class="f-icon">🌐</div>
          <div class="f-title">联网搜索</div>
          <div class="f-desc">实时获取开放时间、票价变动与最新资讯</div>
        </div>
        <div class="feature">
          <div class="f-icon">📚</div>
          <div class="f-title">RAG 知识增强</div>
          <div class="f-desc">向量知识库覆盖热门景点与旅行攻略</div>
        </div>
      </div>
    </a-card>

    <a-card title="🔥 热门目的地" style="margin-top: 16px">
      <div class="city-grid">
        <div v-for="c in cities" :key="c" class="city-card" @click="goCity(c)">
          <div class="city-name">{{ c }}</div>
          <div class="city-go">让 AI 规划 →</div>
        </div>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { spotApi } from '../api/trips'

const router = useRouter()
const cities = ref<string[]>(['北京', '上海', '西安', '成都', '杭州', '三亚', '东京', '巴黎'])

onMounted(async () => {
  try {
    const list = await spotApi.cities()
    if (list?.length) cities.value = list.slice(0, 10)
  } catch {
    /* 使用默认城市 */
  }
})

const goCity = (city: string) => {
  router.push({ path: '/chat', query: { q: `我想去${city}，帮我规划一次难忘的旅行` } })
}
</script>

<style scoped>
.hero { background: linear-gradient(135deg, #e8f3ff 0%, #f5f6f8 60%); }
.features {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 16px; margin-top: 30px;
}
.feature { background: #fff; border: 1px solid #e5e6eb; border-radius: 10px; padding: 18px; }
.f-icon { font-size: 28px; }
.f-title { font-weight: 600; margin: 8px 0 4px; }
.f-desc { color: #86909c; font-size: 13px; line-height: 1.5; }
.city-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 12px; }
.city-card {
  border: 1px solid #e5e6eb; border-radius: 10px; padding: 18px 14px;
  cursor: pointer; transition: all 0.2s;
}
.city-card:hover { border-color: #165dff; transform: translateY(-2px); box-shadow: 0 6px 16px rgba(22,93,255,0.1); }
.city-name { font-weight: 600; font-size: 16px; }
.city-go { color: #165dff; font-size: 13px; margin-top: 6px; }
</style>
