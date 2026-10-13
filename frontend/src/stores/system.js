import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchMeta, fetchReadiness } from '@/api/system'

export const useSystemStore = defineStore('system', () => {
  const meta = ref(null)
  const readiness = ref(null)
  const error = ref('')

  async function load() {
    error.value = ''
    try {
      ;[meta.value, readiness.value] = await Promise.all([fetchMeta(), fetchReadiness()])
    } catch {
      error.value = 'API не отвечает. Проверьте, что backend запущен.'
    }
  }

  return { meta, readiness, error, load }
})
