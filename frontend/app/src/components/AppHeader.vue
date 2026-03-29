<!--
  Шапка приложения.
  Содержит логотип, меню пользователя с ролью, ссылки навигации
  (оценка для Judge, просмотр результатов для Viewer/Admin) и кнопку выхода.
-->
<script setup>
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const menuOpen = ref(false)

const isOnResultsPage = computed(() => !!route.meta.viewerMode)

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function closeMenu() {
  menuOpen.value = false
}

function goToResults() {
  closeMenu()
  router.push({ name: 'results-sheets' })
}

function goToJudge() {
  closeMenu()
  router.push({ name: 'sheets' })
}

async function logout() {
  closeMenu()
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <header class="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-gray-200 bg-white px-4 sm:px-6 dark:border-gray-700 dark:bg-gray-800">
    <router-link to="/" class="flex items-center gap-2 text-base font-semibold text-gray-800 no-underline dark:text-gray-200">
      <svg class="text-primary" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9 11l3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </svg>
      <span>Жюри SK</span>
    </router-link>

    <div v-if="auth.user" class="relative">
      <!-- Profile icon button -->
      <button
        class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border-none bg-primary-light text-primary transition hover:bg-primary hover:text-white"
        @click="toggleMenu"
      >
        <svg class="h-5 w-5" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.501 20.118a7.5 7.5 0 0 1 14.998 0A17.933 17.933 0 0 1 12 21.75c-2.676 0-5.216-.584-7.499-1.632Z" />
        </svg>
      </button>

      <!-- Dropdown overlay -->
      <div v-if="menuOpen" class="fixed inset-0 z-20" @click="closeMenu"></div>

      <!-- Dropdown menu -->
      <div
        v-if="menuOpen"
        class="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-gray-200 bg-white py-2 shadow-lg dark:border-gray-700 dark:bg-gray-800"
      >
        <div class="border-b border-gray-100 px-4 py-2 dark:border-gray-700">
          <p class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ auth.user.nickname || auth.user.email }}</p>
          <span v-if="auth.roleName" class="mt-0.5 inline-block rounded-full bg-primary-light px-2 py-0.5 text-xs font-medium text-primary">{{ auth.roleName }}</span>
        </div>
        <button
          v-if="auth.isViewer && !isOnResultsPage"
          class="flex w-full cursor-pointer items-center gap-2 border-none bg-transparent px-4 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
          @click="goToResults"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" /></svg>
          Просмотр результатов
        </button>
        <button
          v-if="auth.isJudge && isOnResultsPage"
          class="flex w-full cursor-pointer items-center gap-2 border-none bg-transparent px-4 py-2 text-left text-sm text-gray-700 transition hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700"
          @click="goToJudge"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L10.582 16.07a4.5 4.5 0 0 1-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 0 1 1.13-1.897l8.932-8.931Zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0 1 15.75 21H5.25A2.25 2.25 0 0 1 3 18.75V8.25A2.25 2.25 0 0 1 5.25 6H10" /></svg>
          Оценка работ
        </button>
        <button
          class="flex w-full cursor-pointer items-center gap-2 border-none bg-transparent px-4 py-2 text-left text-sm text-red-600 transition hover:bg-gray-50 dark:text-red-400 dark:hover:bg-gray-700"
          @click="logout"
        >
          <svg class="h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6a2.25 2.25 0 0 0-2.25 2.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3 0 3-3m0 0-3-3m3 3H9" /></svg>
          Выйти
        </button>
      </div>
    </div>
  </header>
</template>
