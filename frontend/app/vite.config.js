import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(() => {
  const apiUrl = process.env.VITE_API_URL || 'https://flow.skeducator.ru'
  const backendProxyUrl = process.env.VITE_BACKEND_API_PROXY_URL || 'http://localhost:8000/api/v1'

  return {
    plugins: [vue(), tailwindcss()],
    resolve: {
      alias: { '@': '/src' },
    },
    server: {
      proxy: {
        '/api': {
          target: apiUrl,
          changeOrigin: true,
          secure: true,
        },
        '/backend': {
          target: backendProxyUrl,
          changeOrigin: true,
          secure: false,
          rewrite: (path) => path.replace(/^\/backend/, ''),
        },
      },
    },
  }
})
