<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const account = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function handleLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(account.value, password.value)
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.errors?.[0]?.message || 'Неверный логин или пароль'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="flex flex-1 items-start justify-center p-6 pt-10 sm:pt-24">
    <form class="w-full max-w-md rounded-xl bg-white p-10 shadow-lg dark:bg-gray-800" @submit.prevent="handleLogin">
      <div class="mb-4 flex justify-center text-primary">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 11l3 3L22 4" />
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
        </svg>
      </div>
      <h1 class="mb-1 text-center text-xl font-semibold text-gray-900 dark:text-gray-100">Вход в систему</h1>
      <p class="mb-7 text-center text-sm text-gray-500 dark:text-gray-400">Оценка конкурсных работ</p>

      <div class="mb-4">
        <label for="account" class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">Логин или email</label>
        <input
          id="account"
          v-model="account"
          type="text"
          placeholder="Введите логин"
          required
          autofocus
          class="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 transition focus:border-primary focus:ring-2 focus:ring-primary-light focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
        />
      </div>

      <div class="mb-4">
        <label for="password" class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">Пароль</label>
        <input
          id="password"
          v-model="password"
          type="password"
          placeholder="Введите пароль"
          required
          class="w-full rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 text-sm text-gray-900 transition focus:border-primary focus:ring-2 focus:ring-primary-light focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-100"
        />
      </div>

      <p v-if="error" class="mb-3 text-sm text-red-600">{{ error }}</p>

      <button
        type="submit"
        :disabled="loading"
        class="w-full cursor-pointer rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-white transition hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-50"
      >
        {{ loading ? 'Вход...' : 'Войти' }}
      </button>
    </form>
  </div>
</template>

<style scoped>
</style>
