<!--
  Список оценочных листов.
  Фильтрация по роли и статусу листа (active/inactive/archived):
    - Judge: только active листы, в которых пользователь числится в судьях.
    - Viewer: active + inactive листы (без архивных).
    - Admin: все листы.
-->
<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const sheets = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await api.get('/contest_evaluation_sheets:list', {
      params: {
        appends: 'judges,contest,stage',
        pageSize: 200,
      },
    })
    // Фильтрация по статусу листа и роли пользователя
    // status: active | inactive | archived (если отсутствует — считаем inactive)
    const allSheets = data.data || []
    const personId = auth.personId

    if (auth.isJudge && personId) {
      // Жюри видит только active листы, в которых состоит
      sheets.value = allSheets.filter((sheet) => {
        const status = sheet.status || 'inactive'
        if (status !== 'active') return false
        if (!sheet.judges || !Array.isArray(sheet.judges)) return false
        return sheet.judges.some((j) => j.id === personId)
      })
    } else if (auth.isViewer) {
      // Viewer видит active и inactive (не archived)
      sheets.value = allSheets.filter((sheet) => {
        const status = sheet.status || 'inactive'
        return status === 'active' || status === 'inactive'
      })
    } else {
      // Admin видит всё
      sheets.value = allSheets
    }
  } catch (e) {
    error.value = 'Не удалось загрузить оценочные листы'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div>
    <h1 class="mb-5 text-2xl font-bold text-gray-900 dark:text-gray-100">Оценочные листы</h1>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка...</span>
    </div>

    <p v-else-if="error" class="py-12 text-center text-red-600">{{ error }}</p>

    <p v-else-if="!sheets.length" class="py-12 text-center text-gray-500">
      Нет доступных оценочных листов
    </p>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3" v-else>
      <router-link
        v-for="sheet in sheets"
        :key="sheet.id"
        :to="{ name: 'works', params: { sheetId: sheet.id } }"
        class="block rounded-xl border border-gray-200 bg-white p-5 no-underline shadow-sm transition hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
      >
        <h3 class="mb-1 text-base font-semibold text-gray-900 dark:text-gray-100">{{ sheet.title }}</h3>
        <p v-if="sheet.contest?.title" class="mb-3 text-sm text-gray-500 dark:text-gray-400">{{ sheet.contest.title }}</p>
        <div class="flex flex-wrap items-center gap-2">
          <span v-if="sheet.stage?.title" class="inline-block rounded-full bg-primary-light px-3 py-0.5 text-xs font-medium text-primary">{{ sheet.stage.title }}</span>
          <span
            v-if="!auth.isJudge && (sheet.status || 'inactive') !== 'active'"
            class="inline-block rounded-full px-3 py-0.5 text-xs font-medium"
            :class="(sheet.status || 'inactive') === 'archived' ? 'bg-gray-200 text-gray-600 dark:bg-gray-600 dark:text-gray-300' : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'"
          >
            {{ (sheet.status || 'inactive') === 'archived' ? 'Архивный' : 'Неактивный' }}
          </span>
        </div>
      </router-link>
    </div>
  </div>
</template>
