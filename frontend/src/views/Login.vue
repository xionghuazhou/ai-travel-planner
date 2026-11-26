<template>
  <div class="login-wrapper">
    <a-card class="login-card">
      <h2 style="text-align: center; margin: 0 0 6px">🧳 TravelAI</h2>
      <p style="text-align: center; color: #86909c; margin: 0 0 20px">
        登录后开启你的 AI 旅行规划之旅
      </p>
      <a-form :model="form" layout="vertical" @submit-success="submit">
        <a-form-item field="username" label="用户名" :rules="[{ required: true, message: '请输入用户名' }]">
          <a-input v-model="form.username" placeholder="用户名" allow-clear />
        </a-form-item>
        <a-form-item v-if="mode === 'register'" field="email" label="邮箱" :rules="[{ required: true, message: '请输入邮箱' }]">
          <a-input v-model="form.email" placeholder="邮箱" allow-clear />
        </a-form-item>
        <a-form-item field="password" label="密码" :rules="[{ required: true, message: '请输入密码' }]">
          <a-input-password v-model="form.password" placeholder="至少 6 位密码" />
        </a-form-item>
        <a-button type="primary" html-type="submit" long :loading="loading">
          {{ mode === 'login' ? '登录' : '注册并登录' }}
        </a-button>
      </a-form>
      <div style="text-align: center; margin-top: 14px">
        <a-link @click="toggleMode">
          {{ mode === 'login' ? '没有账号？立即注册' : '已有账号？去登录' }}
        </a-link>
      </div>
    </a-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Message } from '@arco-design/web-vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const mode = ref<'login' | 'register'>('login')
const loading = ref(false)
const form = reactive({ username: '', email: '', password: '' })

const toggleMode = () => {
  mode.value = mode.value === 'login' ? 'register' : 'login'
}

const submit = async () => {
  loading.value = true
  try {
    if (mode.value === 'login') {
      await auth.login(form.username, form.password)
    } else {
      await auth.register(form.username, form.email, form.password)
    }
    Message.success('登录成功')
    router.push((route.query.redirect as string) || '/chat')
  } catch (e: any) {
    Message.error(e?.detail || e?.message || '操作失败')
  } finally {
    loading.value = false
  }
}
</script>
