<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import api from '../api'

const AUTO_REFRESH_INTERVAL = 30000 // 30 секунд

const props = defineProps({
  sheetId: [String, Number],
  workId: [String, Number],
})

const sheet = ref(null)
const work = ref(null)
const criteria = ref([])
const levelsMap = reactive({})  // { [scale_id]: levels[] }
const judges = ref([])          // [{ judge, evaluation, items: { [criterion_id]: item } }]
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const expandedComments = reactive({}) // { 'judge_id-criterion_id': true }
const expandedGeneralComments = reactive({}) // { judge_id: true }
const expandedCriteria = reactive({}) // { evaluation_id: true }
let refreshTimer = null

async function loadData(isRefresh = false) {
  if (isRefresh) refreshing.value = true
  else loading.value = true
  error.value = ''

  try {
    const [sheetRes, workRes] = await Promise.all([
      api.get('/contest_evaluation_sheets:get', {
        params: { filterByTk: props.sheetId },
      }),
      api.get('/contest_evaluation_sheet_works:get', {
        params: {
          filterByTk: props.workId,
          appends: 'stage_participation,stage_participation.participation,stage_participation.participation.participants,stage_participation.participation.supervisors',
        },
      }),
    ])
    sheet.value = sheetRes.data.data
    work.value = workRes.data.data

    // Загружаем критерии
    const scorecardId = sheet.value.scorecard_id
    const criteriaRes = await api.get('/contest_scorecard_criteria:list', {
      params: {
        filter: JSON.stringify({ scorecard_id: scorecardId }),
        sort: 'order,id',
        pageSize: 200,
      },
    })
    criteria.value = criteriaRes.data.data || []

    // Загружаем уровни для всех шкал
    const scaleIds = [...new Set(criteria.value.map((c) => c.scale_id).filter(Boolean))]
    if (scaleIds.length) {
      // Очищаем старые данные
      for (const key of Object.keys(levelsMap)) delete levelsMap[key]
      const levelsRes = await api.get('/contest_criterion_scale_levels:list', {
        params: {
          filter: JSON.stringify({ scale_id: { $in: scaleIds } }),
          sort: 'order,id',
          pageSize: 500,
        },
      })
      for (const level of levelsRes.data.data || []) {
        if (!levelsMap[level.scale_id]) levelsMap[level.scale_id] = []
        levelsMap[level.scale_id].push(level)
      }
    }

    // Загружаем ВСЕ оценки для этой работы (все судьи)
    const evalRes = await api.get('/contest_evaluations:list', {
      params: {
        filter: JSON.stringify({ sheet_work_id: Number(props.workId) }),
        appends: 'judge',
        pageSize: 200,
      },
    })
    const evaluations = evalRes.data.data || []

    // Загружаем items для всех оценок
    const evalIds = evaluations.map((ev) => ev.id)
    let allItems = []
    if (evalIds.length) {
      const itemsRes = await api.get('/contest_evaluation_items:list', {
        params: {
          filter: JSON.stringify({ evaluation_id: { $in: evalIds } }),
          pageSize: 2000,
        },
      })
      allItems = itemsRes.data.data || []
    }

    // Группируем items по evaluation_id
    const itemsByEval = {}
    for (const item of allItems) {
      if (!itemsByEval[item.evaluation_id]) itemsByEval[item.evaluation_id] = {}
      itemsByEval[item.evaluation_id][item.criterion_id] = item
    }

    // Собираем данные по судьям
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

function getParticipants() {
  return work.value?.stage_participation?.participation?.participants || []
}

function getSupervisors() {
  return work.value?.stage_participation?.participation?.supervisors || []
}

function getLevelTitle(criterion, item) {
  if (!item?.level_id) return null
  const levels = levelsMap[criterion.scale_id] || []
  return levels.find((l) => l.id === item.level_id)?.title || null
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
      <router-link
        :to="{ name: 'works', params: { sheetId: props.sheetId } }"
        class="text-sm text-primary no-underline hover:underline"
      >
        &larr; К списку работ
      </router-link>
      <button
        @click="loadData(true)"
        :disabled="refreshing"
        class="flex cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-600 shadow-sm transition hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700"
      >
        <svg class="h-4 w-4" :class="refreshing ? 'animate-spin' : ''" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.992 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182M20.016 4.356v4.992" /></svg>
        {{ refreshing ? 'Обновление...' : 'Обновить' }}
      </button>
    </div>

    <div class="mb-2" v-if="work">
      <h1 class="mb-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{{ getWorkTitle() }}</h1>
      <p v-if="sheet?.title" class="text-sm text-gray-500 dark:text-gray-400">{{ sheet.title }}</p>
      <div v-if="getParticipants().length" class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        <span class="font-medium">Участники:</span> {{ getParticipants().map(p => p.full_name || p.short_name).join(', ') }}
      </div>
      <div v-if="getSupervisors().length" class="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
        <span class="font-medium">Руководители:</span> {{ getSupervisors().map(s => s.full_name || s.short_name).join(', ') }}
      </div>
      <div class="mt-1 text-sm text-gray-600 dark:text-gray-400" v-if="work.score != null">
        <span class="font-medium">Итого:</span> {{ work.score }} б.
        <span v-if="work.rank" class="ml-2 inline-block rounded-full bg-primary-light px-2.5 py-0.5 text-xs font-medium text-primary">{{ work.rank }} место</span>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка...</span>
    </div>

    <p v-else-if="error" class="py-12 text-center text-red-600">{{ error }}</p>

    <template v-else>
      <p v-if="!judges.length" class="py-8 text-center text-gray-500">Нет оценок для этой работы</p>

      <!-- Judges list -->
      <div class="mt-4 flex flex-col gap-4">
        <div
          v-for="j in judges"
          :key="j.evaluation.id"
          class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800"
        >
          <!-- Judge header -->
          <div class="mb-3 flex items-center justify-between">
            <h3 class="text-base font-semibold text-gray-900 dark:text-gray-100">
              {{ j.judge?.full_name || j.judge?.short_name || 'Судья' }}
            </h3>
            <span class="rounded-full bg-primary-light px-3 py-0.5 text-sm font-semibold text-primary">
              Итого: {{ j.evaluation.score ?? '—' }}
            </span>
          </div>

          <!-- Toggle criteria -->
          <button
            class="mb-2 flex w-full cursor-pointer items-center gap-1.5 border-none bg-transparent p-0 font-sans text-sm font-medium text-primary hover:underline"
            @click="toggleCriteria(j.evaluation.id)"
          >
            <svg
              class="h-4 w-4 transition-transform"
              :class="expandedCriteria[j.evaluation.id] ? 'rotate-90' : ''"
              viewBox="0 0 20 20" fill="currentColor"
            ><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
            {{ expandedCriteria[j.evaluation.id] ? 'Скрыть оценки по критериям' : 'Показать оценки по критериям' }}
          </button>

          <!-- Criteria scores (collapsible) -->
          <div v-if="expandedCriteria[j.evaluation.id]" class="flex flex-col gap-2">
            <div
              v-for="criterion in criteria"
              :key="criterion.id"
              class="rounded-lg border border-gray-100 bg-gray-50 px-4 py-2.5 dark:border-gray-700 dark:bg-gray-900/30"
            >
              <div class="flex items-center justify-between gap-3">
                <span class="text-sm text-gray-700 dark:text-gray-300">{{ criterion.title }}</span>
                <div class="flex shrink-0 items-center gap-2">
                  <span
                    class="rounded-full px-2 py-0.5 text-sm font-semibold"
                    :class="j.items[criterion.id]?.level_id != null
                      ? 'bg-primary-light text-primary'
                      : 'bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500'"
                  >
                    {{ j.items[criterion.id]?.score ?? '—' }}
                  </span>
                  <button
                    v-if="j.items[criterion.id]?.comment"
                    class="cursor-pointer border-none bg-transparent p-0 text-xs text-primary hover:underline"
                    @click="toggleComment(j.evaluation.id, criterion.id)"
                  >
                    {{ expandedComments[`${j.evaluation.id}-${criterion.id}`] ? 'Скрыть' : 'Комментарий' }}
                  </button>
                </div>
              </div>
              <!-- Level title -->
              <p
                v-if="getLevelTitle(criterion, j.items[criterion.id])"
                class="mt-0.5 text-xs text-gray-500 dark:text-gray-400"
              >
                {{ getLevelTitle(criterion, j.items[criterion.id]) }}
              </p>
              <!-- Expanded comment -->
              <p
                v-if="expandedComments[`${j.evaluation.id}-${criterion.id}`] && j.items[criterion.id]?.comment"
                class="mt-1.5 whitespace-pre-wrap rounded-md bg-white px-3 py-2 text-sm text-gray-600 dark:bg-gray-800 dark:text-gray-400"
              >
                {{ j.items[criterion.id].comment }}
              </p>
            </div>
          </div>

          <!-- General comment -->
          <div class="mt-3 border-t border-gray-200 pt-3 dark:border-gray-700">
            <button
              v-if="j.evaluation.comment"
              class="cursor-pointer border-none bg-transparent p-0 font-sans text-sm text-primary hover:underline"
              @click="toggleGeneralComment(j.evaluation.id)"
            >
              {{ expandedGeneralComments[j.evaluation.id] ? 'Скрыть общий комментарий' : 'Показать общий комментарий' }}
            </button>
            <span v-else class="text-sm text-gray-400">Нет общего комментария</span>
            <p
              v-if="expandedGeneralComments[j.evaluation.id] && j.evaluation.comment"
              class="mt-2 whitespace-pre-wrap rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-600 dark:bg-gray-900/30 dark:text-gray-400"
            >
              {{ j.evaluation.comment }}
            </p>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
