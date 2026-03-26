/**
 * HTTP-клиент для взаимодействия с NocoBase REST API.
 *
 * Базовый URL: /api (проксируется через Vite dev-сервер или nginx в продакшене).
 * NocoBase использует формат эндпоинтов <collection>:<action>,
 * например: /api/contest_evaluations:list, /api/auth:signIn.
 *
 * Перехватчики:
 * - request: подставляет Bearer-токен из localStorage.
 * - response: при 401 (истёкшая сессия) очищает токен и редиректит на логин.
 */
import axios from 'axios'
import router from '../router'

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Автоматическая подстановка JWT-токена в каждый запрос
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Глобальная обработка ошибки авторизации
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
    }
    return Promise.reject(error)
  },
)

export default api
