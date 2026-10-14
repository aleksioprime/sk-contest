import { http } from './http'

export async function fetchProviders() {
  const { data } = await http.get('/v1/auth/providers')
  return data
}

export async function requestMagicLink(email, next, captchaToken = null) {
  const { data } = await http.post('/v1/auth/magic-link', { email, next, captcha_token: captchaToken })
  return data
}

export async function verifyMagicLink(token) {
  const { data } = await http.post('/v1/auth/magic-link/verify', { token })
  return data
}

/** Текущий пользователь и признак режима судьи (интерфейс только с оценочными листами). */
export async function fetchMe() {
  const { data } = await http.get('/v1/auth/me')
  return data
}

export async function logout() {
  await http.post('/v1/auth/logout')
}

export function skolstreamLoginUrl(next = '/') {
  return `/api/v1/auth/skolstream/login?next=${encodeURIComponent(next)}`
}

export async function loginWithPassword(email, password, next) {
  const { data } = await http.post('/v1/auth/login', { email, password, next })
  return data
}

export async function changePassword(currentPassword, newPassword) {
  await http.post('/v1/auth/password', { current_password: currentPassword || null, new_password: newPassword })
}
