import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const person = ref(null)
  const token = ref(localStorage.getItem('token') || '')

  const isAuthenticated = computed(() => !!token.value)
  const personId = computed(() => person.value?.id ?? null)

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

  return { user, person, personId, token, isAuthenticated, login, fetchUser, logout }
})
