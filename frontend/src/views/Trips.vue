<template>
  <div class="page-container">
    <a-empty v-if="!loading && trips.length === 0" description="还没有行程，去让 AI 帮你规划一次吧">
      <a-button type="primary" @click="$router.push('/chat')">开始 AI 行程规划</a-button>
    </a-empty>

    <a-spin v-if="loading" style="display: block; margin: 60px auto" />

    <div class="trip-grid">
      <a-card v-for="t in trips" :key="t.id" hoverable class="trip-card" @click="$router.push(`/trips/${t.id}`)">
        <div class="trip-card-body">
          <div class="trip-title">{{ t.title }}</div>
          <div class="trip-meta">
            <span>📍 {{ t.destination }}</span>
            <span>📅 {{ t.start_date }} ~ {{ t.end_date }}</span>
            <span>👥 {{ t.travelers }} 人</span>
            <span>💰 ¥{{ t.budget?.toLocaleString() }}</span>
          </div>
          <div class="trip-footer">
            <a-tag :color="t.status === 'confirmed' ? 'green' : 'blue'">
              {{ { planning: '规划中', confirmed: '已确认', in_progress: '旅途中', completed: '已完成', cancelled: '已取消' }[t.status] || t.status }}
            </a-tag>
            <a-button size="mini" type="text" status="danger" @click.stop="removeTrip(t.id)">删除</a-button>
          </div>
        </div>
      </a-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Message } from '@arco-design/web-vue'
import { tripApi, type Trip } from '../api/trips'

const trips = ref<Trip[]>([])
const loading = ref(true)

const load = async () => {
  loading.value = true
  try {
    trips.value = await tripApi.list()
  } catch {
    Message.error('行程加载失败')
  } finally {
    loading.value = false
  }
}

const removeTrip = async (id: string) => {
  try {
    await tripApi.remove(id)
    trips.value = trips.value.filter((t) => t.id !== id)
    Message.success('已删除')
  } catch {
    Message.error('删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.trip-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px; }
.trip-title { font-size: 16px; font-weight: 600; margin-bottom: 8px; }
.trip-meta { display: flex; flex-wrap: wrap; gap: 12px; color: #4e5969; font-size: 13px; margin-bottom: 10px; }
.trip-footer { display: flex; justify-content: space-between; align-items: center; }
</style>
