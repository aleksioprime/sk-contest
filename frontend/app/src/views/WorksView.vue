<!--
  Список работ в оценочном листе.

  Judge-режим: карточки работ со статусом оценки («Оценено» / «Не оценено»).
  Viewer-режим: карточки с результатами (баллы, место),
               сортировка, автообновление каждые 30 секунд.

  API-загрузка:
    1) Лист + работы
    2) Для Judge — оценки текущего пользователя
-->
<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'

/** Интервал автообновления данных для Viewer (мс) */
const AUTO_REFRESH_INTERVAL = 30000
const WORKS_SORT_STORAGE_KEY = 'sk-contest.works.sortBy'

const props = defineProps({ sheetId: [String, Number] })
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const viewerMode = computed(() => !!route.meta.viewerMode)

const sheet = ref(null)
const works = ref([])
const evaluationsMap = ref({}) // { sheet_work_id: evaluation } — оценки текущего судьи
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const sortBy = ref('total')     // 'total' | 'order' — текущая сортировка
let refreshTimer = null

const hasUnscoredWorks = computed(() => works.value.some((work) => !work.is_scored))

/**
 * Опции сортировки: по общему баллу и по порядку.
 */
const sortOptions = computed(() => {
  return [
    { value: 'total', label: 'По общему баллу' },
    { value: 'order', label: 'По порядку' },
  ]
})

function restoreSortPreference() {
  if (typeof window === 'undefined') return
  const stored = window.localStorage.getItem(WORKS_SORT_STORAGE_KEY)
  if (stored === 'total' || stored === 'order') {
    sortBy.value = stored
  }
}

function persistSortPreference(value) {
  if (typeof window === 'undefined') return
  if (value === 'total' || value === 'order') {
    window.localStorage.setItem(WORKS_SORT_STORAGE_KEY, value)
  }
}

function getWorkOrderValue(work) {
  return work?.order != null ? Number(work.order) : Number.POSITIVE_INFINITY
}

function getWorkScoreValue(work) {
  if (work?.score == null) return null
  const score = Number(work.score)
  return Number.isNaN(score) ? null : score
}

function compareBySheetOrder(a, b) {
  const orderDiff = getWorkOrderValue(a) - getWorkOrderValue(b)
  if (orderDiff !== 0) return orderDiff
  return Number(a.id) - Number(b.id)
}

const liveRankMap = computed(() => {
  const ranked = [...works.value]
    .filter((w) => getWorkScoreValue(w) != null)
    .sort((a, b) => {
      const diff = getWorkScoreValue(b) - getWorkScoreValue(a)
      return diff !== 0 ? diff : compareBySheetOrder(a, b)
    })

  const map = {}
  let previousScore = null
  let previousRank = null

  for (let i = 0; i < ranked.length; i++) {
    const work = ranked[i]
    const score = getWorkScoreValue(work)
    if (previousScore == null || Math.abs(score - previousScore) > 1e-9) {
      previousRank = i + 1
      previousScore = score
    }
    map[work.id] = previousRank
  }
  return map
})

function getLiveRank(work) {
  return liveRankMap.value[work.id] ?? null
}

function getDbRank(work) {
  if (work?.rank == null || work.rank === '') return null
  const rank = Number(work.rank)
  return Number.isNaN(rank) ? null : rank
}

function hasRankMismatch(work) {
  const dbRank = getDbRank(work)
  if (dbRank == null) return false
  return getLiveRank(work) !== dbRank
}

const sortedWorks = computed(() => {
  const sorted = [...works.value].sort(compareBySheetOrder)
  if (!viewerMode.value) return sorted

  if (sortBy.value === 'order') return sorted
  // По общему баллу
  return sorted.sort((a, b) => {
    const ra = getLiveRank(a)
    const rb = getLiveRank(b)
    if (ra != null && rb != null) return ra - rb || compareBySheetOrder(a, b)
    if (ra != null) return -1
    if (rb != null) return 1
    return compareBySheetOrder(a, b)
  })
})

/**
 * Загрузка данных страницы.
 * Выполняет загрузку в 2 этапа:
 *   1) Оценочный лист + работы
 *   2) Для Judge: оценки текущего пользователя
 * @param {boolean} isRefresh — true при фоновом обновлении (не показывает спиннер)
 */
async function loadData(isRefresh = false) {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  error.value = ''

  try {
    evaluationsMap.value = {}

    const [sheetRes, worksRes] = await Promise.all([
      api.get('/contest_evaluation_sheets:get', {
        params: { filterByTk: props.sheetId, appends: 'observers,contest,stage' },
      }),
      api.get('/contest_evaluation_sheet_works:list', {
        params: {
          filter: JSON.stringify({ sheet_id: props.sheetId }),
          appends: 'stage_participation,stage_participation.participation,stage_participation.participation.participants,stage_participation.participation.supervisors',
          sort: 'order,id',
          pageSize: 200,
        },
      }),
    ])
    sheet.value = sheetRes.data.data
    works.value = worksRes.data.data || []

    const personId = auth.personId != null ? Number(auth.personId) : null
    const userId = auth.user?.id != null ? Number(auth.user.id) : null
    const canObserveSheet = (targetSheet) => {
      if (auth.isAdmin) return true
      const observers = Array.isArray(targetSheet?.observers) ? targetSheet.observers : []
      return observers.some((observer) => {
        const observerId = observer?.id != null ? Number(observer.id) : null
        const observerUserId = observer?.user_id != null ? Number(observer.user_id) : null
        if (personId != null && observerId === personId) return true
        if (userId != null && (observerId === userId || observerUserId === userId)) return true
        return false
      })
    }
    if (viewerMode.value && auth.isViewer && !canObserveSheet(sheet.value)) {
      router.replace({ name: 'results-sheets' })
      return
    }

    // Проверяем доступ по статусу листа
    const status = sheet.value.status || 'inactive'
    if (status === 'archived' && !viewerMode.value) {
      router.replace('/')
      return
    }
    if (status !== 'active' && !viewerMode.value) {
      router.replace('/')
      return
    }

    // Загружаем оценки текущего судьи (для Judge)
    const workIds = works.value.map((w) => w.id)

    // Для жюри — оценки текущего пользователя
    let judgeEvals = []
    if (!viewerMode.value && auth.isJudge) {
      const personId = auth.personId
      if (personId && workIds.length) {
        const { data } = await api.get('/contest_evaluations:list', {
          params: {
            filter: JSON.stringify({ sheet_work_id: { $in: workIds }, judge_id: personId }),
            pageSize: 200,
          },
        })
        judgeEvals = data.data || []
      }
    }

    // Карта оценок жюри
    if (!viewerMode.value) {
      const newEvalsMap = {}
      for (const ev of judgeEvals) {
        newEvalsMap[ev.sheet_work_id] = ev
      }
      evaluationsMap.value = newEvalsMap

      // Показываем судье только работы, к которым он назначен (есть запись в contest_evaluations)
      works.value = works.value.filter((w) => !!newEvalsMap[w.id])
    }
  } catch (e) {
    if (!isRefresh) error.value = 'Не удалось загрузить работы'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => {
  if (viewerMode.value) {
    restoreSortPreference()
  }
  loadData()
  if (viewerMode.value) {
    refreshTimer = setInterval(() => loadData(true), AUTO_REFRESH_INTERVAL)
  }
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

watch(sortBy, (value) => {
  if (viewerMode.value) {
    persistSortPreference(value)
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

function getParticipation(work) {
  return work.stage_participation?.participation || null
}

function formatParticipantName(participant) {
  return participant.full_name || participant.short_name || 'Участник'
}

function getParticipantsLabel(work) {
  const names = getParticipants(work).map(formatParticipantName).filter(Boolean)
  return names.join(', ')
}

function isExternalWork(work) {
  return !!getParticipation(work)?.is_external
}

function getSupervisors(work) {
  return work.stage_participation?.participation?.supervisors || []
}

function getJudgeEvaluation(work) {
  return evaluationsMap.value[work.id] || null
}

/** Проверка, оценены ли все критерии для данной работы текущим судьёй */
function isFullyEvaluated(work) {
  const ev = evaluationsMap.value[work.id]
  return !!ev?.is_scored
}
</script>

<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <router-link :to="viewerMode ? { name: 'results-sheets' } : '/'" class="text-sm text-primary no-underline hover:underline">&larr; К оценочным листам</router-link>
      <button
        v-if="viewerMode"
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

    <div
      v-if="viewerMode && !loading && !error && works.length && hasUnscoredWorks"
      class="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-900/20 dark:text-amber-200"
    >
      <span class="font-semibold">Внимание:</span>
      не все работы в этом оценочном листе оценены. Текущее ранжирование и распределение мест являются предварительными и могут измениться после завершения оценивания.
    </div>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка...</span>
    </div>

    <p v-else-if="error" class="py-12 text-center text-red-600">{{ error }}</p>

    <p v-else-if="!works.length" class="py-12 text-center text-gray-500">
      Нет работ для оценки
    </p>

    <template v-else>
      <!-- Sort dropdown (viewer only) -->
      <div v-if="viewerMode" class="mb-3 flex items-center gap-2">
        <label for="sort-select" class="text-sm text-gray-600 dark:text-gray-400">Сортировка:</label>
        <select
          id="sort-select"
          v-model="sortBy"
          class="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 shadow-sm dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
        >
          <option v-for="opt in sortOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
        </select>
      </div>

    <div class="flex flex-col gap-3">
      <router-link
        v-for="work in sortedWorks"
        :key="work.id"
        :to="{ name: viewerMode ? 'results-evaluation' : 'evaluation', params: { sheetId: props.sheetId, workId: work.id } }"
        class="flex flex-col items-start gap-3 rounded-xl border border-gray-200 bg-white px-5 py-4 no-underline shadow-sm transition hover:shadow-md sm:flex-row sm:items-center sm:gap-4 dark:border-gray-700 dark:bg-gray-800"
      >
        <div class="min-w-0 w-full flex-1">
          <div class="mb-1 flex flex-wrap items-center gap-2">
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">{{ getWorkTitle(work) }}</h3>
            <span
              v-if="isExternalWork(work)"
              class="inline-block rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
            >
              Внешний участник
            </span>
          </div>
          <div v-if="getParticipants(work).length" class="mb-0.5 text-sm text-gray-600 dark:text-gray-400">
            <span class="font-medium">Участники:</span> {{ getParticipantsLabel(work) }}
          </div>
          <div v-if="getSupervisors(work).length" class="text-sm text-gray-500 dark:text-gray-400">
            <span class="font-medium">Руководители:</span> {{ getSupervisors(work).map(s => s.full_name || s.short_name).join(', ') }}
          </div>
        </div>
        <!-- Viewer: баллы и ранг -->
        <template v-if="viewerMode">
          <div class="flex w-full flex-wrap items-center gap-2 sm:w-auto sm:justify-end">
            <span v-if="work.score != null" class="shrink-0 rounded-full bg-score-light px-3 py-1 text-sm font-bold text-score">
              {{ work.score }}
            </span>
            <span
              class="shrink-0 rounded-full px-3 py-0.5 text-xs font-medium"
              :class="work.is_scored ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'"
            >
              {{ work.is_scored ? 'Работа оценена' : 'Работа не оценена' }}
            </span>
            <span
              v-if="getLiveRank(work) != null || hasRankMismatch(work)"
              class="shrink-0 rounded-full px-3 py-0.5 text-xs font-medium"
              :class="hasRankMismatch(work) ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' : 'bg-primary-light text-primary'"
            >
              {{ getLiveRank(work) != null ? `${getLiveRank(work)} место` : 'Пересчёт: —' }}
            </span>
            <span
              v-if="hasRankMismatch(work) && getDbRank(work) != null"
              class="shrink-0 rounded-full bg-yellow-100 px-3 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300"
            >
              БД: {{ getDbRank(work) }} место
            </span>
          </div>
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
    </template>
  </div>
</template>

<style scoped>
</style>
