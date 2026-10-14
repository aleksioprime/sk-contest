import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as api from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const judgeMode = ref(false)
  const loaded = ref(false)

  const isAuthenticated = computed(() => !!user.value)
  const isAdmin = computed(() => !!user.value?.is_superuser)
  const displayName = computed(() => user.value?.person?.short_name || user.value?.email || '')

  async function load(force = false) {
    if (loaded.value && !force) return user.value
    try {
      const me = await api.fetchMe()
      user.value = me.user
      judgeMode.value = me.judge_mode
    } catch {
      user.value = null
      judgeMode.value = false
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
      judgeMode.value = false
    }
  }

  return { user, judgeMode, loaded, isAuthenticated, isAdmin, displayName, load, setUser, logout }
})
