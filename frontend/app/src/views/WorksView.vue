<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ sheetId: [String, Number] })
const auth = useAuthStore()

const sheet = ref(null)
const works = ref([])
const evaluationsMap = ref({}) // { sheet_work_id: evaluation }
const criteriaCount = ref(0)
const itemsCountMap = ref({}) // { evaluation_id: count of items with level_id }
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [sheetRes, worksRes] = await Promise.all([
      api.get('/contest_evaluation_sheets:get', {
        params: { filterByTk: props.sheetId, appends: 'contest,stage' },
      }),
      api.get('/contest_evaluation_sheet_works:list', {
        params: {
          filter: JSON.stringify({ sheet_id: props.sheetId }),
          appends: 'stage_participation,stage_participation.participation,stage_participation.participation.participants,stage_participation.participation.supervisors',
          pageSize: 200,
        },
      }),
    ])
    sheet.value = sheetRes.data.data
    works.value = worksRes.data.data || []

    // Загружаем количество критериев для scorecard
    const scorecardId = sheet.value.scorecard_id
    if (scorecardId) {
      const criteriaRes = await api.get('/contest_scorecard_criteria:list', {
        params: {
          filter: JSON.stringify({ scorecard_id: scorecardId }),
          pageSize: 200,
        },
      })
      criteriaCount.value = (criteriaRes.data.data || []).length
    }

    // Загружаем оценки текущего жюри
    const personId = auth.personId
    if (personId && works.value.length) {
      const workIds = works.value.map((w) => w.id)
      const evalRes = await api.get('/contest_evaluations:list', {
        params: {
          filter: JSON.stringify({
            sheet_work_id: { $in: workIds },
            judge_id: personId,
          }),
          pageSize: 200,
        },
      })
      const evals = evalRes.data.data || []
      for (const ev of evals) {
        evaluationsMap.value[ev.sheet_work_id] = ev
      }

      // Загружаем evaluation_items для всех оценок, чтобы определить полноту
      const evalIds = evals.map((ev) => ev.id)
      if (evalIds.length) {
        const itemsRes = await api.get('/contest_evaluation_items:list', {
          params: {
            filter: JSON.stringify({ evaluation_id: { $in: evalIds } }),
            pageSize: 1000,
          },
        })
        for (const item of itemsRes.data.data || []) {
          if (item.level_id != null) {
            itemsCountMap.value[item.evaluation_id] = (itemsCountMap.value[item.evaluation_id] || 0) + 1
          }
        }
      }
    }
  } catch (e) {
    error.value = 'Не удалось загрузить работы'
  } finally {
    loading.value = false
  }
})

function getWorkTitle(work) {
  return work.stage_participation?.title
    || work.stage_participation?.participation?.title
    || `Работа #${work.id}`
}

function getParticipants(work) {
  return work.stage_participation?.participation?.participants || []
}

function getSupervisors(work) {
  return work.stage_participation?.participation?.supervisors || []
}

function getJudgeEvaluation(work) {
  return evaluationsMap.value[work.id] || null
}

function isFullyEvaluated(work) {
  const ev = evaluationsMap.value[work.id]
  if (!ev || !criteriaCount.value) return false
  return (itemsCountMap.value[ev.id] || 0) >= criteriaCount.value
}
</script>

<template>
  <div>
    <router-link to="/" class="mb-4 inline-block text-sm text-primary no-underline hover:underline">&larr; К оценочным листам</router-link>

    <h1 class="mb-1 text-2xl font-bold text-gray-900 dark:text-gray-100" v-if="sheet">{{ sheet.title }}</h1>
    <p v-if="sheet?.contest?.title" class="mb-5 text-sm text-gray-500 dark:text-gray-400">{{ sheet.contest.title }}</p>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка...</span>
    </div>

    <p v-else-if="error" class="py-12 text-center text-red-600">{{ error }}</p>

    <p v-else-if="!works.length" class="py-12 text-center text-gray-500">
      Нет работ для оценки
    </p>

    <div class="flex flex-col gap-3" v-else>
      <router-link
        v-for="work in works"
        :key="work.id"
        :to="{ name: 'evaluation', params: { sheetId: props.sheetId, workId: work.id } }"
        class="flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 no-underline shadow-sm transition hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
      >
        <div class="min-w-0 flex-1">
          <h3 class="mb-1 text-base font-semibold text-gray-900 dark:text-gray-100">{{ getWorkTitle(work) }}</h3>
          <div v-if="getParticipants(work).length" class="mb-0.5 text-sm text-gray-600 dark:text-gray-400">
            <span class="font-medium">Участники:</span> {{ getParticipants(work).map(p => p.full_name || p.short_name).join(', ') }}
          </div>
          <div v-if="getSupervisors(work).length" class="text-sm text-gray-500 dark:text-gray-400">
            <span class="font-medium">Руководители:</span> {{ getSupervisors(work).map(s => s.full_name || s.short_name).join(', ') }}
          </div>
        </div>
        <span
          v-if="isFullyEvaluated(work)"
          class="shrink-0 rounded-full bg-green-100 px-3 py-0.5 text-xs font-medium text-green-600"
        >
          Оценено
        </span>
        <span v-else class="shrink-0 rounded-full bg-amber-100 px-3 py-0.5 text-xs font-medium text-amber-600">Не оценено</span>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
</style>
