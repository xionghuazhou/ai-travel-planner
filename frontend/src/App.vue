<template>
  <a-layout class="app-layout">
    <a-layout-header class="app-header">
      <div class="header-inner">
        <div class="logo" @click="$router.push('/')">🧳 TravelAI · 旅行智脑</div>
        <a-menu mode="horizontal" :selected-keys="[activeMenu]" class="nav-menu">
          <a-menu-item key="home" @click="$router.push('/')">首页</a-menu-item>
          <a-menu-item key="chat" @click="$router.push('/chat')">AI 行程规划</a-menu-item>
          <a-menu-item key="trips" @click="$router.push('/trips')">我的行程</a-menu-item>
        </a-menu>
        <div class="header-right">
          <template v-if="user">
            <a-avatar :size="30" style="background: #165dff">{{ user.username[0]?.toUpperCase() }}</a-avatar>
            <span class="username">{{ user.username }}</span>
            <a-button size="small" type="text" @click="logout">退出</a-button>
          </template>
          <template v-else>
            <a-button size="small" type="primary" @click="$router.push('/login')">登录</a-button>
          </template>
        </div>
      </div>
    </a-layout-header>
    <a-layout-content>
      <router-view />
    </a-layout-content>
  </a-layout>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const user = computed(() => auth.user)

const activeMenu = computed(() => {
  if (route.path.startsWith('/chat')) return 'chat'
  if (route.path.startsWith('/trip')) return 'trips'
  if (route.path === '/') return 'home'
  return ''
})

const logout = () => {
  localStorage.removeItem('token')
  localStorage.removeItem('user')
  router.push('/login')
}
</script>

<style scoped>
.app-layout { min-height: 100vh; }
.app-header {
  background: #fff; border-bottom: 1px solid #e5e6eb;
  padding: 0; height: 60px; line-height: 60px;
}
.header-inner {
  max-width: 1100px; margin: 0 auto; display: flex; align-items: center; gap: 28px;
  padding: 0 16px;
}
.logo { font-size: 18px; font-weight: 700; cursor: pointer; color: #165dff; white-space: nowrap; }
.nav-menu { flex: 1; border-bottom: none; background: transparent; }
.header-right { display: flex; align-items: center; gap: 8px; height: 60px; }
.username { font-size: 14px; color: #1d2129; }
</style>
