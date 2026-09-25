import axios from 'axios'
import { csrfFromCookie } from '../utils/account'

export function useCsrf(client) {
  client.interceptors.request.use((config) => {
    if (!['get', 'head', 'options'].includes((config.method || 'get').toLowerCase())) {
      // 登录会轮换 cookie；每次提交都读取当前值，不缓存先前的令牌。
      const token = csrfFromCookie(document.cookie)
      if (token) config.headers['X-CSRFToken'] = token
    }
    return config
  })
  return client
}

const http = useCsrf(axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api/v1',
  timeout: 10000,
  withCredentials: true,
}))

export default http
