import axios from 'axios'

export const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: { 'Content-Type': 'application/json' },
})

let refreshing = null
let onUnauthorized = () => {}

/** Вызывается, когда сессию не удалось продлить (роутер отправляет на страницу входа). */
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

const NO_RETRY = ['/v1/auth/refresh', '/v1/auth/magic-link', '/v1/auth/logout']

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { config, response } = error
    if (response?.status !== 401 || config.__retried || NO_RETRY.some((url) => config.url.startsWith(url))) {
      throw error
    }
    config.__retried = true
    try {
      // Несколько запросов с истёкшим токеном ждут одного обновления сессии
      refreshing ??= http.post('/v1/auth/refresh').finally(() => {
        refreshing = null
      })
      await refreshing
    } catch {
      onUnauthorized()
      throw error
    }
    return http(config)
  },
)

/** Текст ошибки API для показа пользователю. */
export function errorMessage(error, fallback = 'Что-то пошло не так. Попробуйте ещё раз.') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail.message === 'string') return detail.message
  if (Array.isArray(detail)) return 'Проверьте правильность заполнения полей'
  if (!error?.response) return 'Сервер недоступен. Проверьте подключение.'
  return fallback
}
