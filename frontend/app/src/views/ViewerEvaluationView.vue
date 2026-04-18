<!--
  Просмотр оценок всех судей по работе (Viewer).

  Отображает карточки судей с раскрывающимися оценками по критериям,
  сгруппированными по категориям (со сворачиванием).
  Автообновление каждые 30 секунд.

  API-загрузка в 3 параллельных раунда:
    1) Лист + работа
    2) Критерии + оценки (с данными судьи)
    3) Категории + уровни + evaluation_items
-->
<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '../api'
import { useAuthStore } from '../stores/auth'

/** Интервал автообновления (мс) */
const AUTO_REFRESH_INTERVAL = 30000 // 30 секунд

const props = defineProps({
  sheetId: [String, Number],
  workId: [String, Number],
})

const auth = useAuthStore()
const router = useRouter()

const sheet = ref(null)
const work = ref(null)
const sheetWorks = ref([])
const criteria = ref([])          // критерии оценочного листа
const categories = ref([])        // категории критериев
const levelsMap = reactive({})    // { scale_id: levels[] } — уровни шкал
const judges = ref([])            // [{ judge, evaluation, items }] — данные по каждому судье
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const expandedComments = reactive({})        // { 'evalId-criterionId': true } — раскрытые комментарии
const expandedGeneralComments = reactive({})  // { evalId: true } — раскрытые общие комментарии
const expandedCriteria = reactive({})         // { evalId: true } — раскрытые блоки критериев
const collapsedCategories = reactive({})      // { 'evalId-catKey': true } — свёрнутые категории
let refreshTimer = null

async function loadData(isRefresh = false) {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  error.value = ''

  try {
    const [sheetRes, workRes, sheetWorksRes] = await Promise.all([
      api.get('/contest_evaluation_sheets:get', {
        params: { filterByTk: props.sheetId, appends: 'observers' },
      }),
      api.get('/contest_evaluation_sheet_works:get', {
        params: {
          filterByTk: props.workId,
          appends: 'stage_participation,stage_participation.participation,stage_participation.participation.participants,stage_participation.participation.supervisors',
        },
      }),
      api.get('/contest_evaluation_sheet_works:list', {
        params: {
          filter: JSON.stringify({ sheet_id: Number(props.sheetId) }),
          sort: 'order,id',
          pageSize: 1000,
        },
      }),
    ])
    sheet.value = sheetRes.data.data
    work.value = workRes.data.data
    sheetWorks.value = sheetWorksRes.data.data || []

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
    if (auth.isViewer && !canObserveSheet(sheet.value)) {
      router.replace({ name: 'results-sheets' })
      return
    }

    // Раунд 2: критерии + оценки параллельно (критерии зависят от sheet, оценки — от workId)
    const scorecardId = sheet.value.scorecard_id
    const [criteriaRes, evalRes] = await Promise.all([
      api.get('/contest_scorecard_criteria:list', {
        params: {
          filter: JSON.stringify({ scorecard_id: scorecardId }),
          sort: 'order,id',
          pageSize: 200,
        },
      }),
      api.get('/contest_evaluations:list', {
        params: {
          filter: JSON.stringify({ sheet_work_id: Number(props.workId) }),
          appends: 'judge',
          pageSize: 200,
        },
      }),
    ])
    criteria.value = criteriaRes.data.data || []
    const evaluations = evalRes.data.data || []

    // Раунд 3: категории + уровни + items параллельно
    const categoryIds = [...new Set(criteria.value.map((c) => c.category_id).filter(Boolean))]
    const scaleIds = [...new Set(criteria.value.map((c) => c.scale_id).filter(Boolean))]
    const evalIds = evaluations.map((ev) => ev.id)

    const parallelRequests = []
    const requestKeys = []

    if (categoryIds.length) {
      parallelRequests.push(api.get('/contest_criterion_categories:list', {
        params: { filter: JSON.stringify({ id: { $in: categoryIds } }), pageSize: 200 },
      }))
      requestKeys.push('categories')
    }
    if (scaleIds.length) {
      parallelRequests.push(api.get('/contest_criterion_scale_levels:list', {
        params: { filter: JSON.stringify({ scale_id: { $in: scaleIds } }), sort: 'order,id', pageSize: 500 },
      }))
      requestKeys.push('levels')
    }
    if (evalIds.length) {
      parallelRequests.push(api.get('/contest_evaluation_items:list', {
        params: { filter: JSON.stringify({ evaluation_id: { $in: evalIds } }), pageSize: 2000 },
      }))
      requestKeys.push('items')
    }

    const parallelResults = await Promise.all(parallelRequests)
    const resultMap = {}
    requestKeys.forEach((key, i) => { resultMap[key] = parallelResults[i] })

    if (resultMap.categories) {
      categories.value = resultMap.categories.data.data || []
    }
    if (resultMap.levels) {
      for (const key of Object.keys(levelsMap)) delete levelsMap[key]
      for (const level of resultMap.levels.data.data || []) {
        if (!levelsMap[level.scale_id]) levelsMap[level.scale_id] = []
        levelsMap[level.scale_id].push(level)
      }
    }
    let allItems = resultMap.items ? (resultMap.items.data.data || []) : []

    // Группируем items по evaluation_id
    const itemsByEval = {}
    for (const item of allItems) {
      if (!itemsByEval[item.evaluation_id]) itemsByEval[item.evaluation_id] = {}
      itemsByEval[item.evaluation_id][item.criterion_id] = item
    }

    // Собираем данные по судьям из оценок (contest_evaluations → judge)
    judges.value = evaluations.map((ev) => ({
      judge: ev.judge,
      evaluation: ev,
      items: itemsByEval[ev.id] || {},
    }))
  } catch (e) {
    if (!isRefresh) error.value = 'Не удалось загрузить данные'
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

onMounted(() => {
  loadData()
  refreshTimer = setInterval(() => loadData(true), AUTO_REFRESH_INTERVAL)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})

function getWorkTitle() {
  if (!work.value) return ''
  const sp = work.value.stage_participation
  return sp?.title || sp?.participation?.title || `Работа #${work.value.id}`
}

function getWorkOrderValue(sheetWork) {
  return sheetWork?.order != null ? Number(sheetWork.order) : Number.POSITIVE_INFINITY
}

function getWorkScoreValue(sheetWork) {
  if (sheetWork?.score == null) return null
  const score = Number(sheetWork.score)
  return Number.isNaN(score) ? null : score
}

function compareBySheetOrder(a, b) {
  const orderDiff = getWorkOrderValue(a) - getWorkOrderValue(b)
  if (orderDiff !== 0) return orderDiff
  return Number(a.id) - Number(b.id)
}

const liveRankMap = computed(() => {
  const ranked = [...sheetWorks.value]
    .filter((w) => getWorkScoreValue(w) != null)
    .sort((a, b) => {
      const diff = getWorkScoreValue(b) - getWorkScoreValue(a)
      return diff !== 0 ? diff : compareBySheetOrder(a, b)
    })

  const map = {}
  let previousScore = null
  let previousRank = null
  for (let i = 0; i < ranked.length; i++) {
    const sheetWork = ranked[i]
    const score = getWorkScoreValue(sheetWork)
    if (previousScore == null || Math.abs(score - previousScore) > 1e-9) {
      previousRank = i + 1
      previousScore = score
    }
    map[sheetWork.id] = previousRank
  }
  return map
})

function getLiveRank() {
  const workId = Number(work.value?.id)
  if (!workId) return null
  return liveRankMap.value[workId] ?? null
}

function getDbRank() {
  if (work.value?.rank == null || work.value.rank === '') return null
  const rank = Number(work.value.rank)
  return Number.isNaN(rank) ? null : rank
}

function hasRankMismatch() {
  const dbRank = getDbRank()
  if (dbRank == null) return false
  return getLiveRank() !== dbRank
}

function getParticipation() {
  return work.value?.stage_participation?.participation || null
}

function isExternalWork() {
  return !!getParticipation()?.is_external
}

function getParticipants() {
  return getParticipation()?.participants || []
}

function getSupervisors() {
  return getParticipation()?.supervisors || []
}

function getPersonName(person) {
  return person?.full_name || person?.short_name || ''
}

function getParticipantsLabel() {
  return getParticipants().map(getPersonName).filter(Boolean).join(', ')
}

function getSupervisorsLabel() {
  return getSupervisors().map(getPersonName).filter(Boolean).join(', ')
}

function getWorkNotes() {
  const notes = getParticipation()?.notes
  return typeof notes === 'string' ? notes.trim() : ''
}

function getLevelTitle(criterion, item) {
  if (!item?.level_id) return null
  const levels = levelsMap[criterion.scale_id] || []
  return levels.find((l) => l.id === item.level_id)?.title || null
}

const hasCategories = computed(() => categories.value.length > 0)

const categoriesMap = computed(() => {
  const map = {}
  for (const cat of categories.value) map[cat.id] = cat
  return map
})

const groupedCriteria = computed(() => {
  if (!hasCategories.value) return [{ category: null, criteria: criteria.value }]
  const groups = {}
  const uncategorized = []
  for (const c of criteria.value) {
    if (c.category_id && categoriesMap.value[c.category_id]) {
      if (!groups[c.category_id]) groups[c.category_id] = []
      groups[c.category_id].push(c)
    } else {
      uncategorized.push(c)
    }
  }
  const result = categories.value
    .filter((cat) => groups[cat.id])
    .map((cat) => ({ category: cat, criteria: groups[cat.id] }))
  if (uncategorized.length) result.push({ category: null, criteria: uncategorized })
  return result
})

/** Балл судьи по категории (сумма оценок критериев категории) */
function judgeCategoryScore(judgeData, categoryId) {
  return criteria.value
    .filter((c) => c.category_id === categoryId)
    .reduce((sum, c) => sum + (judgeData.items[c.id]?.score ? Number(judgeData.items[c.id].score) : 0), 0)
}

/** Проверяет, выставил ли судья хотя бы одну оценку */
function hasJudgeAnyScores(judgeData) {
  return Object.values(judgeData.items).some((item) => item.level_id != null)
}

function isJudgeFullyScored(judgeData) {
  return !!judgeData.evaluation?.is_scored
}

function toggleComment(judgeId, criterionId) {
  const key = `${judgeId}-${criterionId}`
  expandedComments[key] = !expandedComments[key]
}

function toggleGeneralComment(judgeId) {
  expandedGeneralComments[judgeId] = !expandedGeneralComments[judgeId]
}

function toggleCriteria(evalId) {
  expandedCriteria[evalId] = !expandedCriteria[evalId]
}
</script>

<template>
  <div>
    <div class="mb-4 flex items-center justify-between">
      <router-link :to="{ name: 'results-works', params: { sheetId: props.sheetId } }"
        class="text-sm text-primary no-underline hover:underline">
        &larr; К списку работ
      </router-link>
      <button @click="loadData(true)" :disabled="refreshing"
        class="flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700">
        <svg class="h-4 w-4" :class="refreshing ? 'animate-spin' : ''" xmlns="http://www.w3.org/2000/svg" fill="none"
          viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round"
            d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.992 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182M20.016 4.356v4.992" />
        </svg>
        {{ refreshing ? 'Обновление...' : 'Обновить' }}
      </button>
    </div>

    <div class="mb-2" v-if="work">
      <div class="mb-1 flex flex-wrap items-center gap-2">
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ getWorkTitle() }}</h1>
        <div class="items-right">
          <span v-if="isExternalWork()"
            class="inline-block rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300">
            Внешний участник
          </span>
          <span class="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
            :class="work.is_scored ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'">
            {{ work.is_scored ? 'Оценено' : 'Не оценено' }}
          </span>
        </div>
      </div>
      <p v-if="sheet?.title" class="text-sm text-gray-500 dark:text-gray-400">{{ sheet.title }}</p>
      <div v-if="getParticipants().length" class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        <span class="font-medium">Участники:</span> {{ getParticipantsLabel() }}
      </div>
      <div v-if="getSupervisors().length" class="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
        <span class="font-medium">Руководители:</span> {{ getSupervisorsLabel() }}
      </div>
      <div v-if="getWorkNotes()"
        class="mt-1 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-900/20 dark:text-blue-100">
        <span class="font-medium">Примечание:</span> {{ getWorkNotes() }}
      </div>
      <div v-if="work.score != null || getLiveRank() != null || hasRankMismatch()"
        class="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span v-if="work.score != null"
          class="inline-block rounded-full bg-score-light px-3 py-0.5 font-semibold text-score">
          Итоговый балл: {{ work.score }}
        </span>
        <span v-if="getLiveRank() != null || hasRankMismatch()"
          class="inline-block rounded-full px-2.5 py-0.5 text-xs font-medium"
          :class="hasRankMismatch() ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' : 'bg-primary-light text-primary'">
          {{ getLiveRank() != null ? `${getLiveRank()} место` : 'Пересчёт: —' }}
        </span>
        <span v-if="hasRankMismatch() && getDbRank() != null"
          class="inline-block rounded-full bg-yellow-100 px-2.5 py-0.5 text-xs font-medium text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300">
          БД: {{ getDbRank() }} место
        </span>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
      </svg>
      <span>Загрузка...</span>
    </div>

    <p v-else-if="error" class="py-12 text-center text-red-600">{{ error }}</p>

    <template v-else>
      <p v-if="!judges.length" class="py-8 text-center text-gray-500">Нет оценок для этой работы</p>

      <!-- Judges list -->
      <div class="mt-4 flex flex-col gap-4">
        <div v-for="j in judges" :key="j.evaluation.id"
          class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <!-- Judge header -->
          <div class="flex items-center gap-2" :class="hasJudgeAnyScores(j) ? 'mb-3' : ''">
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
              {{ j.judge?.full_name || j.judge?.short_name || 'Судья' }}
            </h3>
            <div class="ml-auto flex shrink-0 items-center gap-2">
              <span class="rounded-full px-3 py-0.5 text-sm font-medium"
                :class="isJudgeFullyScored(j) ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300'">
                {{ isJudgeFullyScored(j) ? 'Оценено' : 'Не оценено' }}
              </span>
              <span v-if="isJudgeFullyScored(j)"
                class="rounded-full bg-score-light px-3 py-0.5 text-sm font-semibold text-score">
                Баллы: {{ j.evaluation.score ?? '—' }}
              </span>
            </div>
          </div>

          <!-- Content: criteria & comments (only if judge has any scores) -->
          <template v-if="hasJudgeAnyScores(j)">
            <!-- Toggle criteria -->
            <button
              class="mb-2 flex w-full cursor-pointer items-center gap-1.5 border-none bg-transparent p-0 font-sans text-sm font-medium text-primary hover:underline"
              @click="toggleCriteria(j.evaluation.id)">
              <svg class="h-4 w-4 transition-transform" :class="expandedCriteria[j.evaluation.id] ? 'rotate-90' : ''"
                viewBox="0 0 20 20" fill="currentColor">
                <path fill-rule="evenodd"
                  d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                  clip-rule="evenodd" />
              </svg>
              {{ expandedCriteria[j.evaluation.id] ? 'Скрыть оценки по критериям' : 'Показать оценки по критериям' }}
            </button>

            <!-- Criteria scores (collapsible), grouped by categories -->
            <div v-if="expandedCriteria[j.evaluation.id]" class="flex flex-col gap-2">
              <template v-for="group in groupedCriteria" :key="group.category?.id ?? 'uncategorized'">
                <!-- Category block wrapper (styled only when categories exist) -->
                <div :class="hasCategories ? 'mt-1 overflow-hidden rounded-lg border border-primary/20' : ''">
                  <button v-if="hasCategories && group.category"
                    class="flex w-full cursor-pointer items-center justify-between border-none bg-primary/10 px-3 py-1.5 font-sans dark:bg-primary/20"
                    @click="collapsedCategories[`${j.evaluation.id}-${group.category.id}`] = !collapsedCategories[`${j.evaluation.id}-${group.category.id}`]">
                    <div class="flex items-center gap-1.5">
                      <svg class="h-3.5 w-3.5 text-primary transition-transform"
                        :class="collapsedCategories[`${j.evaluation.id}-${group.category.id}`] ? '' : 'rotate-90'"
                        viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd"
                          d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                          clip-rule="evenodd" />
                      </svg>
                      <span class="text-xs font-bold text-primary">{{ group.category.title }}</span>
                    </div>
                    <span class="rounded-full bg-score-light px-2 py-0.5 text-xs font-semibold text-score">{{
                      judgeCategoryScore(j, group.category.id) }}</span>
                  </button>
                  <button v-else-if="hasCategories && !group.category"
                    class="flex w-full cursor-pointer items-center justify-between border-none bg-gray-200/60 px-3 py-1.5 font-sans dark:bg-gray-600/40"
                    @click="collapsedCategories[`${j.evaluation.id}-uncategorized`] = !collapsedCategories[`${j.evaluation.id}-uncategorized`]">
                    <div class="flex items-center gap-1.5">
                      <svg class="h-3.5 w-3.5 text-gray-500 transition-transform"
                        :class="collapsedCategories[`${j.evaluation.id}-uncategorized`] ? '' : 'rotate-90'"
                        viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd"
                          d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z"
                          clip-rule="evenodd" />
                      </svg>
                      <span class="text-xs font-bold text-gray-600 dark:text-gray-300">Без категории</span>
                    </div>
                  </button>
                  <div
                    v-show="!hasCategories || !collapsedCategories[`${j.evaluation.id}-${group.category?.id ?? 'uncategorized'}`]"
                    :class="hasCategories ? 'flex flex-col gap-2 p-2' : 'flex flex-col gap-2'">
                    <div v-for="criterion in group.criteria" :key="criterion.id"
                      class="rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-gray-700 dark:bg-gray-900/30">
                      <div class="flex items-center justify-between gap-3">
                        <div>
                          <span class="text-sm text-gray-700 dark:text-gray-300">{{ criterion.title }}</span>
                          <p v-if="criterion.description"
                            class="m-0 mt-0.5 text-xs leading-relaxed text-gray-400 dark:text-gray-500">{{
                              criterion.description }}</p>
                        </div>
                        <div class="flex shrink-0 items-center gap-2">
                          <span class="rounded-full px-2 py-0.5 text-sm font-semibold" :class="j.items[criterion.id]?.level_id != null
                            ? 'bg-score-light text-score'
                            : 'bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500'">
                            {{ j.items[criterion.id]?.score ?? '—' }}
                          </span>
                          <button v-if="j.items[criterion.id]?.comment"
                            class="cursor-pointer border-none bg-transparent p-0 text-xs text-primary hover:underline"
                            @click="toggleComment(j.evaluation.id, criterion.id)">
                            {{ expandedComments[`${j.evaluation.id}-${criterion.id}`] ? 'Скрыть' : 'Комментарий' }}
                          </button>
                        </div>
                      </div>
                      <!-- Level title -->
                      <p v-if="getLevelTitle(criterion, j.items[criterion.id])"
                        class="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                        {{ getLevelTitle(criterion, j.items[criterion.id]) }}
                      </p>
                      <!-- Expanded comment -->
                      <p v-if="expandedComments[`${j.evaluation.id}-${criterion.id}`] && j.items[criterion.id]?.comment"
                        class="mt-1.5 whitespace-pre-wrap rounded-md bg-white px-3 py-2 text-sm text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                        {{ j.items[criterion.id].comment }}
                      </p>
                    </div>
                  </div><!-- end criteria list -->
                </div><!-- end category block -->
              </template>
            </div>

            <!-- General comment -->
            <div class="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
              <button v-if="j.evaluation.comment"
                class="cursor-pointer border-none bg-transparent p-0 font-sans text-sm text-primary hover:underline"
                @click="toggleGeneralComment(j.evaluation.id)">
                {{ expandedGeneralComments[j.evaluation.id] ? 'Скрыть общий комментарий' : 'Показать общий комментарий'
                }}
              </button>
              <span v-else class="text-sm text-gray-400">Нет общего комментария</span>
              <p v-if="expandedGeneralComments[j.evaluation.id] && j.evaluation.comment"
                class="mt-2 whitespace-pre-wrap rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-600 dark:bg-gray-900/30 dark:text-gray-400">
                {{ j.evaluation.comment }}
              </p>
            </div>
          </template><!-- end v-if evaluation -->
          <p v-else class="text-sm text-gray-400">Оценки не выставлены</p>
        </div>
      </div>
    </template>
  </div>
</template>
