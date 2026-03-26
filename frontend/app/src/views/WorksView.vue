<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const AUTO_REFRESH_INTERVAL = 30000

const props = defineProps({ sheetId: [String, Number] })
const auth = useAuthStore()
const router = useRouter()

const sheet = ref(null)
const works = ref([])
const evaluationsMap = ref({}) // { sheet_work_id: evaluation }
const criteriaCount = ref(0)
const itemsCountMap = ref({}) // { evaluation_id: count of items with level_id }
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
let refreshTimer = null

const sortedWorks = computed(() => {
  if (auth.isJudge) return works.value
  return [...works.value].sort((a, b) => {
    if (a.rank && b.rank) return a.rank - b.rank
    if (a.rank) return -1
    if (b.rank) return 1
    const sa = a.score != null ? Number(a.score) : -1
    const sb = b.score != null ? Number(b.score) : -1
    return sb - sa
  })
})

async function loadData(isRefresh = false) {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  error.value = ''

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

    // Проверяем доступ по статусу листа
    const status = sheet.value.status || 'inactive'
    if (status === 'archived' && !auth.isViewer) {
      router.replace('/')
      return
    }
    if (status !== 'active' && auth.isJudge) {
      router.replace('/')
      return
    }

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

    // Для жюри загружаем оценки и items для проверки полноты
    if (auth.isJudge) {
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
        const newEvalsMap = {}
        for (const ev of evals) {
          newEvalsMap[ev.sheet_work_id] = ev
        }
        evaluationsMap.value = newEvalsMap

        // Загружаем evaluation_items для всех оценок, чтобы определить полноту
        const evalIds = evals.map((ev) => ev.id)
        const newItemsCount = {}
        if (evalIds.length) {
          const itemsRes = await api.get('/contest_evaluation_items:list', {
            params: {
              filter: JSON.stringify({ evaluation_id: { $in: evalIds } }),
              pageSize: 1000,
            },
          })
          for (const item of itemsRes.data.data || []) {
            if (item.level_id != null) {
              newItemsCount[item.evaluation_id] = (newItemsCount[item.evaluation_id] || 0) + 1
            }
          }
        }
        itemsCountMap.value = newItemsCount
      }
    }
  } catch (e) {
    if (!isRefresh) error.value = 'Не удалось загрузить работы'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => {
  loadData()
  if (!auth.isJudge) {
    refreshTimer = setInterval(() => loadData(true), AUTO_REFRESH_INTERVAL)
  }
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
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
    <div class="mb-4 flex items-center justify-between">
      <router-link to="/" class="text-sm text-primary no-underline hover:underline">&larr; К оценочным листам</router-link>
      <button
        v-if="!auth.isJudge"
        @click="loadData(true)"
        :disabled="refreshing"
        class="flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
      >
        <svg class="h-4 w-4" :class="refreshing ? 'animate-spin' : ''" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.992 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182M20.016 4.356v4.992" /></svg>
        {{ refreshing ? 'Обновление...' : 'Обновить' }}
      </button>
    </div>

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
        v-for="work in sortedWorks"
        :key="work.id"
        :to="{ name: auth.isJudge ? 'evaluation' : 'viewer-evaluation', params: { sheetId: props.sheetId, workId: work.id } }"
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
        <!-- Viewer: баллы и ранг -->
        <template v-if="!auth.isJudge">
          <span v-if="work.score != null" class="shrink-0 text-sm font-medium text-gray-600 dark:text-gray-400">
            {{ work.score }} б.
          </span>
          <span v-if="work.rank" class="shrink-0 rounded-full bg-primary-light px-3 py-0.5 text-xs font-medium text-primary">
            {{ work.rank }} место
          </span>
        </template>
        <!-- Judge: статус оценки -->
        <template v-else>
          <span
            v-if="isFullyEvaluated(work)"
            class="shrink-0 rounded-full bg-green-100 px-3 py-0.5 text-xs font-medium text-green-600"
          >
            Оценено
          </span>
          <span v-else class="shrink-0 rounded-full bg-amber-100 px-3 py-0.5 text-xs font-medium text-amber-600">Не оценено</span>
        </template>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
</style>
