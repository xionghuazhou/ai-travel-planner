import { defineStore } from 'pinia'
import { authApi, type User } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: (() => {
      try {
        return JSON.parse(localStorage.getItem('user') || 'null') as User | null
      } catch {
        return null
      }
    })(),
  }),
  actions: {
    async login(username: string, password: string) {
      const res = await authApi.login({ username, password })
      this.token = res.access_token
      this.user = res.user
      localStorage.setItem('token', res.access_token)
      localStorage.setItem('user', JSON.stringify(res.user))
    },
    async register(username: string, email: string, password: string) {
      const res = await authApi.register({ username, email, password })
      this.token = res.access_token
      this.user = res.user
      localStorage.setItem('token', res.access_token)
      localStorage.setItem('user', JSON.stringify(res.user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
