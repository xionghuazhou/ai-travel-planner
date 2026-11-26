import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'home', component: () => import('../views/Home.vue') },
  { path: '/chat', name: 'chat', component: () => import('../views/AIChat.vue') },
  { path: '/trips', name: 'trips', component: () => import('../views/Trips.vue'), meta: { requiresAuth: true } },
  { path: '/trips/:id', name: 'trip-detail', component: () => import('../views/TripDetail.vue'), meta: { requiresAuth: true } },
  { path: '/create', name: 'create', component: () => import('../views/TripCreate.vue'), meta: { requiresAuth: true } },
  { path: '/login', name: 'login', component: () => import('../views/Login.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
})

export default router
