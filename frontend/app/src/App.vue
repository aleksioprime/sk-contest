<!--
  Корневой компонент приложения.
  Задаёт общий layout: шапка (скрывается на странице входа), контентная область и footer.
-->
<script setup>
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'

const route = useRoute()
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <AppHeader v-if="route.name !== 'login'" />
    <main class="mx-auto w-full max-w-5xl flex-1 px-4 py-6 sm:px-6 lg:px-8">
      <router-view />
    </main>
    <footer class="border-t border-gray-200 bg-white px-4 py-4 text-center text-xs text-gray-400 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-500">
      Сервисы автоматизации Гимназии Сколково · © {{ new Date().getFullYear() }}  Алексей Семочкин
    </footer>
  </div>
</template>
