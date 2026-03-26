/**
 * Хранилище авторизации и ролевой модели.
 *
 * Логика ролей:
 *   - Judge (JUDGE_ROLE) — может оценивать работы.
 *   - Viewer (VIEWER_ROLE или admin) — может просматривать оценки всех судей.
 *   - Пользователь с обеими ролями может переключаться через switchMode().
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
  const activeMode = ref(localStorage.getItem('activeMode') || null) // 'judge' | 'viewer' | null — режим для пользователей с двумя ролями

  const isAuthenticated = computed(() => !!token.value)
  const personId = computed(() => person.value?.id ?? null) // ID персоны = judge_id в оценках

  const userRoleNames = computed(() => {
    if (!user.value?.roles) return []
    return user.value.roles.map((r) => r.name)
  })

  const hasJudgeRole = computed(() => userRoleNames.value.includes(JUDGE_ROLE))
  const hasViewerRole = computed(() => userRoleNames.value.includes(VIEWER_ROLE) || userRoleNames.value.includes('admin')) // Admin имеет права Viewer
  const isBothRoles = computed(() => hasJudgeRole.value && hasViewerRole.value)

  // Если у пользователя обе роли — роль определяется текущим activeMode
  const isJudge = computed(() => {
    if (isBothRoles.value) return activeMode.value === 'judge'
    return hasJudgeRole.value
  })
  const isViewer = computed(() => {
    if (isBothRoles.value) return activeMode.value === 'viewer'
    return hasViewerRole.value
  })
  const hasAccess = computed(() => hasJudgeRole.value || hasViewerRole.value)

  const roleName = computed(() => {
    if (isBothRoles.value) {
      return activeMode.value === 'judge' ? 'Judge' : 'Viewer'
    }
    if (hasJudgeRole.value) return 'Judge'
    if (userRoleNames.value.includes('admin')) return 'Admin'
    if (userRoleNames.value.includes(VIEWER_ROLE)) return 'Viewer'
    return null
  })

  /**
   * Переключение режима Judge ↔ Viewer.
   * Сохраняет выбор в localStorage для персистентности между сессиями.
   */
  function switchMode() {
    if (!isBothRoles.value) return
    activeMode.value = activeMode.value === 'judge' ? 'viewer' : 'judge'
    localStorage.setItem('activeMode', activeMode.value)
  }

  /** Устанавливает режим по умолчанию (judge) при первом входе пользователя с двумя ролями */
  function ensureActiveMode() {
    if (isBothRoles.value && !['judge', 'viewer'].includes(activeMode.value)) {
      activeMode.value = 'judge'
      localStorage.setItem('activeMode', 'judge')
    }
  }

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
    ensureActiveMode()
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

  return { user, person, personId, token, isAuthenticated, isJudge, isViewer, isBothRoles, hasAccess, roleName, activeMode, switchMode, login, fetchUser, logout }
})
