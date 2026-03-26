<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-6 dark:border-gray-700 dark:bg-gray-800">
    <router-link to="/" class="flex items-center gap-2 text-base font-semibold text-gray-800 no-underline dark:text-gray-200">
      <svg class="text-primary" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
      Оценка конкурсов
    </router-link>
    <div class="flex items-center gap-3" v-if="auth.user">
      <span class="text-sm text-gray-500 dark:text-gray-400">{{ auth.user.nickname || auth.user.email }}</span>
      <button
        class="cursor-pointer rounded-lg border border-gray-200 bg-transparent px-3 py-1.5 text-sm text-gray-600 transition hover:bg-gray-100 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
        @click="logout"
      >
        Выйти
      </button>
    </div>
  </header>
</template>

<style scoped>
</style>
