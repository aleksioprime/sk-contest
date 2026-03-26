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
const criteriaList = ref([])    // all criteria for this scorecard
const categories = ref([])      // criterion categories
const allEvaluations = ref([])  // all evaluations for all works (viewer mode)
const allItems = ref([])        // all evaluation_items (viewer mode)
const itemsCountMap = ref({}) // { evaluation_id: count of items with level_id }
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const sortBy = ref('total')     // 'total' | 'rank' | category_id
let refreshTimer = null

const hasCategories = computed(() => categories.value.length > 0)

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

// Предвычисленная карта: { workId: { categoryId: avgScore } }
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

function workCategoryScore(workId, categoryId) {
  return categoryScoresCache.value[workId]?.[categoryId] ?? 0
}

// Кэш category scores для текущей сортировки
const workCategoryScores = computed(() => {
  if (sortBy.value === 'total' || sortBy.value === 'rank' || !hasCategories.value) return {}
  const catId = sortBy.value
  const map = {}
  for (const w of works.value) {
    map[w.id] = categoryScoresCache.value[w.id]?.[catId] ?? 0
  }
  return map
})

const sortedWorks = computed(() => {
  if (auth.isJudge) return works.value

  const sorted = [...works.value]
  if (sortBy.value === 'rank') {
    return sorted.sort((a, b) => {
      if (a.rank && b.rank) return a.rank - b.rank
      if (a.rank) return -1
      if (b.rank) return 1
      return 0
    })
  }
  if (sortBy.value !== 'total' && hasCategories.value) {
    // Сортировка по категории
    return sorted.sort((a, b) => {
      const sa = workCategoryScores.value[a.id] ?? 0
      const sb = workCategoryScores.value[b.id] ?? 0
      return sb - sa
    })
  }
  // По общему баллу
  return sorted.sort((a, b) => {
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
    if (auth.isJudge) {
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
    if (!auth.isJudge && workIds.length) {
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
    criteriaCount.value = loadedCriteria.length

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
    if (!auth.isJudge && allEvaluations.value.length && categoryIds.length) {
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

    // Evaluation items для жюри (проверка полноты)
    if (auth.isJudge && judgeEvals.length) {
      const evalIds = judgeEvals.map((ev) => ev.id)
      parallelRequests2.push(
        api.get('/contest_evaluation_items:list', {
          params: {
            filter: JSON.stringify({ evaluation_id: { $in: evalIds } }),
            pageSize: 1000,
          },
        }).then((res) => ({ type: 'judgeItems', data: res.data.data || [] }))
      )
    }

    if (parallelRequests2.length) {
      const results2 = await Promise.all(parallelRequests2)
      for (const r of results2) {
        if (r.type === 'categories') categories.value = r.data
        else if (r.type === 'allItems') allItems.value = r.data
        else if (r.type === 'judgeItems') {
          const newItemsCount = {}
          for (const item of r.data) {
            if (item.level_id != null) {
              newItemsCount[item.evaluation_id] = (newItemsCount[item.evaluation_id] || 0) + 1
            }
          }
          itemsCountMap.value = newItemsCount
        }
      }
    }

    // Карта оценок жюри
    if (auth.isJudge) {
      const newEvalsMap = {}
      for (const ev of judgeEvals) {
        newEvalsMap[ev.sheet_work_id] = ev
      }
      evaluationsMap.value = newEvalsMap
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

    <template v-else>
      <!-- Sort dropdown (viewer only, when categories exist) -->
      <div v-if="!auth.isJudge && hasCategories" class="mb-3 flex items-center gap-2">
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
          <!-- Category scores (viewer only) -->
          <div v-if="!auth.isJudge && hasCategories && allItems.length" class="mt-1.5 flex flex-wrap gap-2">
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
        <template v-if="!auth.isJudge">
          <span v-if="work.score != null" class="shrink-0 rounded-full bg-score-light px-3 py-1 text-sm font-bold text-score">
            {{ work.score }}
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
    </template>
  </div>
</template>

<style scoped>
</style>
