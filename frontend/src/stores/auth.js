import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const loaded = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => !!user.value?.is_superuser)
  const displayName = computed(() => user.value?.person?.short_name || user.value?.email || '')

  async function load(force = false) {
    if (loaded.value && !force) return user.value
    try {
      user.value = await api.fetchMe()
    } catch {
      user.value = null
    }
    loaded.value = true
    return user.value
  }

  function setUser(value) {
    user.value = value
    loaded.value = true
  }

  async function logout() {
    try {
      await api.logout()
    } finally {
      user.value = null
    }
  }

  return { user, loaded, isAuthenticated, isAdmin, displayName, load, setUser, logout }
})
