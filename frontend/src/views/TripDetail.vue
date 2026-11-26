<template>
  <div class="page-container">
    <a-spin v-if="loading" style="display: block; margin: 80px auto" />
    <template v-else-if="trip">
      <!-- 行程概览 -->
      <a-card class="trip-overview">
        <div class="overview-header">
          <div>
            <h1 style="margin: 0 0 10px">{{ trip.title }}</h1>
            <div class="trip-meta">
              <span><icon-environment /> {{ trip.destination }}</span>
              <span><icon-calendar /> {{ formatDate(trip.start_date) }} - {{ formatDate(trip.end_date) }}</span>
              <span><icon-team /> {{ trip.travelers }} 人</span>
              <span><icon-money /> ¥{{ trip.budget?.toLocaleString() }}</span>
            </div>
          </div>
          <a-space>
            <a-button type="primary" @click="exportPDF">
              <template #icon><icon-download /></template>
              导出 PDF
            </a-button>
            <a-button @click="$router.push('/chat')">问 AI 修改行程</a-button>
            <a-button status="danger" @click="remove">删除</a-button>
          </a-space>
        </div>
      </a-card>

      <!-- 地图视图 -->
      <a-card title="📍 行程地图（景点分布）" class="map-card" style="margin-top: 16px">
        <div ref="mapContainer" class="map-container"></div>
      </a-card>

      <!-- 每日行程 -->
      <div class="itinerary-days">
        <a-card v-for="day in trip.days" :key="day.id" class="day-card" style="margin-top: 16px">
          <template #title>
            <div class="day-header">
              <div class="day-number">Day {{ day.day_number }}</div>
              <div>{{ formatDate(day.date) }}<span v-if="day.theme"> · {{ day.theme }}</span></div>
            </div>
          </template>

          <div v-if="day.weather_info" class="day-weather">
            <span>{{ day.weather_info.icon || '🌤️' }} {{ day.weather_info.weather }}</span>
            <span>{{ day.weather_info.temp_low }}°C ~ {{ day.weather_info.temp_high }}°C</span>
          </div>

          <a-empty v-if="!day.spots?.length" description="当天暂无具体景点安排（可让 AI 补充规划）" />
          <a-timeline v-else>
            <a-timeline-item
              v-for="(spot, index) in day.spots"
              :key="spot.id || index"
              :color="getSpotColor(index)"
            >
              <div class="spot-item">
                <div class="spot-time">{{ spot.start_time }} - {{ spot.end_time }}</div>
                <div class="spot-info">
                  <div style="font-weight: 600">{{ spot.name }}</div>
                  <div class="spot-meta">
                    <span v-if="spot.category">{{ spot.category }}</span>
                    <span>游览约 {{ spot.duration_minutes }} 分钟</span>
                    <span v-if="spot.estimated_cost">¥{{ spot.estimated_cost }}</span>
                  </div>
                  <div v-if="spot.notes" style="font-size: 13px; color: #4e5969; margin-top: 4px">
                    {{ spot.notes }}
                  </div>
                </div>
              </div>
              <div v-if="spot.transport_to_next" class="transport-info">
                <icon-car /> {{ spot.transport_to_next }}
              </div>
            </a-timeline-item>
          </a-timeline>

          <div v-if="day.summary" style="background: #f7f8fa; border-radius: 8px; padding: 10px 14px; margin-top: 8px">
            <strong>今日总结：</strong>{{ day.summary }}
          </div>
        </a-card>
      </div>
    </template>

    <a-empty v-else description="行程不存在">
      <a-button type="primary" @click="$router.push('/trips')">返回行程列表</a-button>
    </a-empty>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import * as echarts from 'echarts'
import { tripApi, type TripDetail } from '../api/trips'

const route = useRoute()
const router = useRouter()

const trip = ref<TripDetail | null>(null)
const loading = ref(true)
const mapContainer = ref<HTMLElement>()

const load = async () => {
  loading.value = true
  try {
    trip.value = await tripApi.detail(route.params.id as string)
    nextTick(initMap)
  } catch (e: any) {
    Message.error(e?.detail || '行程加载失败')
  } finally {
    loading.value = false
  }
}

const initMap = () => {
  if (!mapContainer.value || !trip.value) return
  const chart = echarts.init(mapContainer.value)
  const seriesData: any[] = []
  const dayColors = ['#165dff', '#00b42a', '#ff7d00', '#722ed1', '#14c9c9', '#f53f3f']
  Promise.all(
    Array.from(new Set(trip.value.days.flatMap((d) => (d.spots || []).map((s) => s.name)))).map((name) =>
      import('../api/trips').then((m) => m.spotApi.list({ q: name, limit: 1 }))
    )
  )
    .then((results) => {
      const byName: Record<string, any> = {}
      results.forEach((list) => {
        if (list?.length) byName[list[0].name] = list[0]
      })
      trip.value!.days.forEach((day) => {
        ;(day.spots || []).forEach((spot, idx) => {
          const ref = byName[spot.name]
          if (ref?.latitude && ref?.longitude) {
            seriesData.push({
              name: spot.name,
              value: [Number(ref.longitude), Number(ref.latitude)],
              day: day.day_number,
              symbolSize: 18,
              itemStyle: { color: dayColors[(day.day_number - 1) % dayColors.length] },
              label: { show: true, formatter: `${spot.name}`, position: 'right', fontSize: 11 },
            })
          }
        })
      })
      chart.setOption({
        backgroundColor: '#f7f8fa',
        tooltip: { formatter: (p: any) => `${p.name}（Day ${p.data.day}）` },
        xAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
        yAxis: { type: 'value', show: false, min: 'dataMin', max: 'dataMax' },
        series: [
          {
            type: 'scatter',
            data: seriesData,
            coordinateSystem: 'cartesian2d',
          },
        ],
      })
    })
    .catch(() => {})
  window.addEventListener('resize', () => chart.resize())
}

const getSpotColor = (index: number) => {
  const colors = ['blue', 'green', 'orange', 'purple', 'cyan']
  return colors[index % colors.length]
}

const formatDate = (dateStr: string) => {
  try {
    return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'short' })
  } catch {
    return dateStr
  }
}

const exportPDF = () => {
  window.print()
}

const remove = async () => {
  try {
    await tripApi.remove(route.params.id as string)
    Message.success('已删除')
    router.push('/trips')
  } catch {
    Message.error('删除失败')
  }
}

onMounted(load)
</script>

<style scoped>
.overview-header { display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px; }
.trip-meta { display: flex; flex-wrap: wrap; gap: 16px; color: #4e5969; }
</style>
