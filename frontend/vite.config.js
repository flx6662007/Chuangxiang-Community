import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const port = Number(process.env.DEV_SERVER_PORT || env.DEV_SERVER_PORT || 5173)
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('DEV_SERVER_PORT must be an integer between 1 and 65535.')
  }

  return {
    plugins: [vue()],
    server: {
      host: '127.0.0.1',
      port,
      strictPort: true,
      proxy: {
        '/api': {
          target: process.env.DEV_PROXY_TARGET || env.DEV_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
  }
})
