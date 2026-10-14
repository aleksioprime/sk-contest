<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { verifyMagicLink } from '@/api/auth'
import { errorMessage } from '@/api/http'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const error = ref('')

onMounted(async () => {
  const token = typeof route.query.token === 'string' ? route.query.token : ''
  if (!token) {
    error.value = 'В ссылке нет кода входа. Запросите новую ссылку.'
    return
  }
  try {
    const result = await verifyMagicLink(token)
    await auth.load(true)
    await router.replace(result.next || '/')
  } catch (e) {
    error.value = errorMessage(e)
  }
})
</script>

<template>
  <main class="grid min-h-dvh place-items-center px-4">
    <div class="w-full max-w-sm rounded-card border border-line bg-surface p-6 text-center">
      <template v-if="error">
        <h1 class="text-xl font-bold">Не получилось войти</h1>
        <p class="mt-2 text-ink-muted">{{ error }}</p>
        <RouterLink :to="{ name: 'login' }" class="mt-5 inline-block font-medium text-brand-600">Запросить новую ссылку</RouterLink>
      </template>
      <p v-else class="text-ink-muted" role="status">Выполняем вход…</p>
    </div>
  </main>
</template>
