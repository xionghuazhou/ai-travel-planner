import axios from 'axios'

// Agent 完整流程包含多次 LLM 调用（解析/生成/反思），推理模型单次可达 60-90 秒，
// 超时需放宽到 300 秒，与 nginx proxy_read_timeout 保持一致。
const request = axios.create({ timeout: 300000 })

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (resp) => resp.data,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (!location.pathname.startsWith('/login')) {
        location.href = `/login?redirect=${encodeURIComponent(location.pathname)}`
      }
    }
    return Promise.reject(error.response?.data || error)
  }
)

export { request }
