/**
 * Хранилище авторизации и ролевой модели.
 *
 * Логика ролей:
 *   - Judge (JUDGE_ROLE) — может оценивать работы.
 *   - Viewer (VIEWER_ROLE или admin) — может просматривать оценки всех судей.
 *   - Пользователь может иметь обе роли одновременно:
 *     по умолчанию открывается оценка, а просмотр результатов доступен через меню.
 *
 * Важно: judge_id в таблице оценок ссылается на person.id (не user.id),
 * поэтому после авторизации загружаем person-запись через fetchPerson().
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

/** Идентификаторы ролей в NocoBase (snowflake-style ID) */
const JUDGE_ROLE = 'r_33jle168sny'
const VIEWER_ROLE = 'r_wrjkkito308'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const person = ref(null)
  const token = ref(localStorage.getItem('token') || '')

  const isAuthenticated = computed(() => !!token.value)
  const personId = computed(() => person.value?.id ?? null) // ID персоны = judge_id в оценках

  const userRoleNames = computed(() => {
    if (!user.value?.roles) return []
    return user.value.roles.map((r) => r.name)
  })

  const isAdmin = computed(() => userRoleNames.value.includes('admin'))
  const hasJudgeRole = computed(() => userRoleNames.value.includes(JUDGE_ROLE))
  const hasViewerRole = computed(() => userRoleNames.value.includes(VIEWER_ROLE) || isAdmin.value) // Admin имеет права Viewer
  const isBothRoles = computed(() => hasJudgeRole.value && hasViewerRole.value)

  // Роли независимы: пользователь может быть одновременно и Judge, и Viewer
  const isJudge = computed(() => hasJudgeRole.value)
  const isViewer = computed(() => hasViewerRole.value)
  const hasAccess = computed(() => hasJudgeRole.value || hasViewerRole.value)

  const roleName = computed(() => {
    const roles = []
    if (hasJudgeRole.value) roles.push('Judge')
    if (isAdmin.value) roles.push('Admin')
    else if (userRoleNames.value.includes(VIEWER_ROLE)) roles.push('Viewer')
    return roles.join(' / ') || null
  })

  /** Авторизация через NocoBase Basic Auth */
  async function login(account, password) {
    const { data } = await api.post('/auth:signIn', { account, password }, {
      headers: { 'X-Authenticator': 'basic' },
    })
    token.value = data.data.token
    localStorage.setItem('token', token.value)
    await fetchUser()
  }

  /** Загрузка профиля пользователя и связанной person-записи */
  async function fetchUser() {
    const { data } = await api.get('/auth:check')
    user.value = data.data
    await fetchPerson()
  }

  /** Находит person-запись по user_id (нужна для сопоставления с judge_id) */
  async function fetchPerson() {
    if (!user.value?.id) return
    try {
      const { data } = await api.get('/persons:list', {
        params: {
          filter: JSON.stringify({ user_id: user.value.id }),
          pageSize: 1,
        },
      })
      person.value = data.data?.[0] || null
    } catch {
      person.value = null
    }
  }

  async function logout() {
    try {
      await api.post('/auth:signOut')
    } catch { /* ignore */ }
    token.value = ''
    user.value = null
    person.value = null
    localStorage.removeItem('token')
  }

  return { user, person, personId, token, isAuthenticated, isJudge, isViewer, isAdmin, isBothRoles, hasAccess, roleName, login, fetchUser, logout }
})
