<template>
  <div class="page-container">
    <a-card title="✨ 手动创建行程" style="max-width: 640px; margin: 0 auto">
      <a-form :model="form" layout="vertical" @submit-success="submit">
        <a-form-item label="目的地" required>
          <a-input v-model="form.destination" placeholder="如：成都" allow-clear />
        </a-form-item>
        <a-form-item label="行程标题">
          <a-input v-model="form.title" placeholder="如：成都三日美食之旅" allow-clear />
        </a-form-item>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="开始日期" required>
              <a-input v-model="form.start_date" placeholder="2026-10-01" allow-clear />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="结束日期" required>
              <a-input v-model="form.end_date" placeholder="2026-10-03" allow-clear />
            </a-form-item>
          </a-col>
        </a-row>
        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item label="预算（元）">
              <a-input-number v-model="form.budget" :min="0" :step="500" style="width: 100%" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item label="出行人数">
              <a-input-number v-model="form.travelers" :min="1" :max="20" style="width: 100%" />
            </a-form-item>
          </a-col>
        </a-row>
        <a-button type="primary" html-type="submit" long :loading="loading">创建行程</a-button>
        <a-alert style="margin-top: 12px" type="info">
          想让 AI 自动规划？前往 <a-link @click="$router.push('/chat')">AI 行程规划</a-link> 页面，一句话生成完整行程。
        </a-alert>
      </a-form>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { tripApi } from '../api/trips'

const router = useRouter()
const loading = ref(false)
const form = reactive({
  title: '',
  destination: '',
  start_date: '',
  end_date: '',
  budget: 5000,
  travelers: 2,
})

const submit = async () => {
  if (!form.destination || !form.start_date || !form.end_date) {
    Message.warning('请填写目的地和日期')
    return
  }
  loading.value = true
  try {
    const trip = await tripApi.create({
      title: form.title || `${form.destination}之旅`,
      destination: form.destination,
      start_date: form.start_date,
      end_date: form.end_date,
      budget: form.budget,
      travelers: form.travelers,
      days: [],
    })
    Message.success('创建成功')
    router.push(`/trips/${trip.id}`)
  } catch (e: any) {
    Message.error(e?.detail || '创建失败')
  } finally {
    loading.value = false
  }
}
</script>
