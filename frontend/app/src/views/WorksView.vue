<!--
  Список работ в оценочном листе.

  Judge-режим: карточки работ со статусом оценки («Оценено» / «Не оценено»).
  Viewer-режим: карточки с результатами (баллы, место, баллы по категориям),
               сортировка, автообновление каждые 30 секунд.

  API-загрузка выполняется в 2 параллельных раунда:
    1) Лист + работы
    2) Критерии + оценки + категории + items
-->
<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'

/** Интервал автообновления данных для Viewer (мс) */
const AUTO_REFRESH_INTERVAL = 30000

const props = defineProps({ sheetId: [String, Number] })
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const viewerMode = computed(() => !!route.meta.viewerMode)

const sheet = ref(null)
const works = ref([])
const evaluationsMap = ref({}) // { sheet_work_id: evaluation } — оценки текущего судьи
const criteriaList = ref([])    // все критерии оценочного листа
const categories = ref([])      // категории критериев
const allEvaluations = ref([])  // все оценки всех судей (режим Viewer)
const allItems = ref([])        // все evaluation_items (режим Viewer)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const sortBy = ref('total')     // 'total' | 'rank' | category_id — текущая сортировка
let refreshTimer = null

const hasCategories = computed(() => categories.value.length > 0)
const hasUnscoredWorks = computed(() => works.value.some((work) => !work.is_scored))

/**
 * Опции сортировки: по общему баллу, по каждой категории, по месту.
 * Категории добавляются динамически на основе загруженных данных.
 */
const sortOptions = computed(() => {
  const opts = [{ value: 'total', label: 'По общему баллу' }]
  if (hasCategories.value) {
    for (const cat of categories.value) {
      opts.push({ value: String(cat.id), label: cat.title })
    }
  }
  opts.push({ value: 'rank', label: 'По месту' })
  return opts
})

/**
 * Предвычисленная карта средних баллов по категориям.
 * Структура: { workId: { categoryId: среднийБалл } }.
 * Средний балл = сумма оценок всех судей по критериям категории / кол-во судей.
 */
const categoryScoresCache = computed(() => {
  if (!hasCategories.value || !allItems.value.length) return {}

  // Группируем criteria по category_id
  const critByCat = {}
  for (const c of criteriaList.value) {
    if (c.category_id) {
      if (!critByCat[c.category_id]) critByCat[c.category_id] = new Set()
      critByCat[c.category_id].add(c.id)
    }
  }

  // Индексируем items по evaluation_id
  const itemsByEval = {}
  for (const item of allItems.value) {
    if (!itemsByEval[item.evaluation_id]) itemsByEval[item.evaluation_id] = []
    itemsByEval[item.evaluation_id].push(item)
  }

  // Группируем evaluations по sheet_work_id
  const evalsByWork = {}
  for (const ev of allEvaluations.value) {
    if (!evalsByWork[ev.sheet_work_id]) evalsByWork[ev.sheet_work_id] = []
    evalsByWork[ev.sheet_work_id].push(ev)
  }

  const result = {}
  for (const w of works.value) {
    const workEvals = evalsByWork[w.id] || []
    if (!workEvals.length) continue
    const catScores = {}
    for (const catId of Object.keys(critByCat)) {
      const criterionIds = critByCat[catId]
      let total = 0
      let judgeCount = 0
      for (const ev of workEvals) {
        const evItems = itemsByEval[ev.id] || []
        let judgeSum = 0
        for (const item of evItems) {
          if (criterionIds.has(item.criterion_id) && item.score != null) {
            judgeSum += Number(item.score)
          }
        }
        total += judgeSum
        judgeCount++
      }
      catScores[catId] = judgeCount ? +(total / judgeCount).toFixed(2) : 0
    }
    result[w.id] = catScores
  }
  return result
})

/** Получить средний балл работы по категории (из кэша) */
function workCategoryScore(workId, categoryId) {
  return categoryScoresCache.value[workId]?.[categoryId] ?? 0
}

// Кэш баллов по выбранной категории для сортировки
const workCategoryScores = computed(() => {
  if (sortBy.value === 'total' || sortBy.value === 'rank' || !hasCategories.value) return {}
  const catId = sortBy.value
  const map = {}
  for (const w of works.value) {
    map[w.id] = categoryScoresCache.value[w.id]?.[catId] ?? 0
  }
  return map
})

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

  if (sortBy.value === 'rank') {
    return sorted.sort((a, b) => {
      const ra = getLiveRank(a)
      const rb = getLiveRank(b)
      if (ra != null && rb != null) return ra - rb || compareBySheetOrder(a, b)
      if (ra != null) return -1
      if (rb != null) return 1
      return compareBySheetOrder(a, b)
    })
  }
  if (sortBy.value !== 'total' && hasCategories.value) {
    // Сортировка по категории
    return sorted.sort((a, b) => {
      const sa = workCategoryScores.value[a.id] ?? 0
      const sb = workCategoryScores.value[b.id] ?? 0
      const diff = sb - sa
      return diff !== 0 ? diff : compareBySheetOrder(a, b)
    })
  }
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
 * Выполняет параллельные API-запросы в 2 раунда:
 *   1) Оценочный лист + работы
 *   2) Критерии, оценки, категории, evaluation_items
 * @param {boolean} isRefresh — true при фоновом обновлении (не показывает спиннер)
 */
async function loadData(isRefresh = false) {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  error.value = ''

  try {
    allEvaluations.value = []
    allItems.value = []
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

    // Загружаем критерии + оценки параллельно (после получения sheet и works)
    const scorecardId = sheet.value.scorecard_id
    const workIds = works.value.map((w) => w.id)

    const parallelRequests = []

    // Критерии (нужны всем)
    if (scorecardId) {
      parallelRequests.push(
        api.get('/contest_scorecard_criteria:list', {
          params: {
            filter: JSON.stringify({ scorecard_id: scorecardId }),
            pageSize: 200,
          },
        }).then((res) => ({ type: 'criteria', data: res.data.data || [] }))
      )
    }

    // Для жюри — оценки текущего пользователя
    if (!viewerMode.value && auth.isJudge) {
      const personId = auth.personId
      if (personId && workIds.length) {
        parallelRequests.push(
          api.get('/contest_evaluations:list', {
            params: {
              filter: JSON.stringify({ sheet_work_id: { $in: workIds }, judge_id: personId }),
              pageSize: 200,
            },
          }).then((res) => ({ type: 'judgeEvals', data: res.data.data || [] }))
        )
      }
    }

    // Для viewer — все оценки
    if (viewerMode.value && workIds.length) {
      parallelRequests.push(
        api.get('/contest_evaluations:list', {
          params: {
            filter: JSON.stringify({ sheet_work_id: { $in: workIds } }),
            pageSize: 500,
          },
        }).then((res) => ({ type: 'allEvals', data: res.data.data || [] }))
      )
    }

    const parallelResults = await Promise.all(parallelRequests)

    let loadedCriteria = []
    let judgeEvals = []

    for (const r of parallelResults) {
      if (r.type === 'criteria') loadedCriteria = r.data
      else if (r.type === 'judgeEvals') judgeEvals = r.data
      else if (r.type === 'allEvals') allEvaluations.value = r.data
    }

    criteriaList.value = loadedCriteria

    // Второй параллельный раунд: категории + evaluation_items
    const parallelRequests2 = []

    // Категории критериев
    const categoryIds = [...new Set(loadedCriteria.map((c) => c.category_id).filter(Boolean))]
    if (categoryIds.length) {
      parallelRequests2.push(
        api.get('/contest_criterion_categories:list', {
          params: {
            filter: JSON.stringify({ id: { $in: categoryIds } }),
            pageSize: 200,
          },
        }).then((res) => ({ type: 'categories', data: res.data.data || [] }))
      )
    } else {
      categories.value = []
    }

    // Evaluation items для viewer (подсчёт по категориям)
    if (viewerMode.value && allEvaluations.value.length && categoryIds.length) {
      const evalIds = allEvaluations.value.map((ev) => ev.id)
      parallelRequests2.push(
        api.get('/contest_evaluation_items:list', {
          params: {
            filter: JSON.stringify({ evaluation_id: { $in: evalIds } }),
            pageSize: 5000,
          },
        }).then((res) => ({ type: 'allItems', data: res.data.data || [] }))
      )
    }

    if (parallelRequests2.length) {
      const results2 = await Promise.all(parallelRequests2)
      for (const r of results2) {
        if (r.type === 'categories') categories.value = r.data
        else if (r.type === 'allItems') allItems.value = r.data
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
  loadData()
  if (viewerMode.value) {
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
      <!-- Sort dropdown (viewer only, when categories exist) -->
      <div v-if="viewerMode && hasCategories" class="mb-3 flex items-center gap-2">
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
        class="flex items-center gap-4 rounded-xl border border-gray-200 bg-white px-5 py-4 no-underline shadow-sm transition hover:shadow-md dark:border-gray-700 dark:bg-gray-800"
      >
        <div class="min-w-0 flex-1">
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
          <!-- Category scores (viewer only) -->
          <div v-if="viewerMode && hasCategories && allItems.length" class="mt-1.5 flex flex-wrap gap-2">
            <span
              v-for="cat in categories"
              :key="cat.id"
              class="inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs"
              :class="sortBy === String(cat.id)
                ? 'ring-1 ring-score bg-score-light text-score'
                : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'"
            >
              <span>{{ cat.title }}</span>
              <strong>{{ workCategoryScore(work.id, cat.id) }}</strong>
            </span>
          </div>
        </div>
        <!-- Viewer: баллы и ранг -->
        <template v-if="viewerMode">
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
