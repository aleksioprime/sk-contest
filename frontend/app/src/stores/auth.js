import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

const JUDGE_ROLE = 'r_33jle168sny'
const VIEWER_ROLE = 'r_wrjkkito308'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const person = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const activeMode = ref(localStorage.getItem('activeMode') || null) // 'judge' | 'viewer' | null

  const isAuthenticated = computed(() => !!token.value)
  const personId = computed(() => person.value?.id ?? null)

  const userRoleNames = computed(() => {
    if (!user.value?.roles) return []
    return user.value.roles.map((r) => r.name)
  })

  const hasJudgeRole = computed(() => userRoleNames.value.includes(JUDGE_ROLE))
  const hasViewerRole = computed(() => userRoleNames.value.includes(VIEWER_ROLE) || userRoleNames.value.includes('admin'))
  const isBothRoles = computed(() => hasJudgeRole.value && hasViewerRole.value)

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

  function switchMode() {
    if (!isBothRoles.value) return
    activeMode.value = activeMode.value === 'judge' ? 'viewer' : 'judge'
    localStorage.setItem('activeMode', activeMode.value)
  }

  function ensureActiveMode() {
    if (isBothRoles.value && !['judge', 'viewer'].includes(activeMode.value)) {
      activeMode.value = 'judge'
      localStorage.setItem('activeMode', 'judge')
    }
  }

  async function login(account, password) {
    const { data } = await api.post('/auth:signIn', { account, password }, {
      headers: { 'X-Authenticator': 'basic' },
    })
    token.value = data.data.token
    localStorage.setItem('token', token.value)
    await fetchUser()
  }

  async function fetchUser() {
    const { data } = await api.get('/auth:check')
    user.value = data.data
    ensureActiveMode()
    await fetchPerson()
  }

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
