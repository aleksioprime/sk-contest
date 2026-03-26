<!--
  Страница оценки работы судьёй (Judge).

  Критерии сгруппированы по категориям с возможностью сворачивания.
  Для каждого критерия отображаются кнопки уровней оценки (сетка 3 столбца на мобильных).
  Оценка сохраняется оптимистично, с откатом при ошибке.

  Внизу страницы — sticky-панель с итоговым баллом и раскладкой по категориям.
  IntersectionObserver отслеживает состояние «прилипания» для динамического скругления углов.

  API-загрузка в 3 параллельных раунда:
    1) Лист + работа
    2) Критерии + оценка судьи
    3) Категории + уровни шкал + evaluation_items
-->
<script setup>
import { ref, reactive, onMounted, onUnmounted, computed, nextTick } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'
import logger from '../utils/logger'

const props = defineProps({
  sheetId: [String, Number],
  workId: [String, Number],
})

const auth = useAuthStore()

const sheet = ref(null)
const work = ref(null)
const evaluation = ref(null)
const criteria = ref([])          // критерии оценочного листа
const categories = ref([])        // категории критериев
const items = reactive({})        // { criterion_id: evaluation_item } — текущие оценки
const levelsMap = reactive({})    // { scale_id: levels[] } — уровни шкал оценивания
const loading = ref(true)
const saving = ref(null)
const error = ref('')
const saved = ref(false)
const collapsedCategories = reactive({}) // { categoryKey: true } — свёрнутые категории
const totalBarStuck = ref(false)         // true, когда панель итогов «прилипла» к низу экрана
const sentinelRef = ref(null)            // ref-элемент для IntersectionObserver
let stickyObserver = null

onUnmounted(() => {
  if (stickyObserver) stickyObserver.disconnect()
})

/**
 * IntersectionObserver для определения, прилипла ли панель итогов к низу.
 * Когда sentinel-элемент уходит за viewport — панель «прилипает»,
 * меняется скругление (rounded-xl → rounded-t-xl).
 */
function initStickyObserver() {
  if (!sentinelRef.value) return
  stickyObserver = new IntersectionObserver(
    ([entry]) => { totalBarStuck.value = !entry.isIntersecting },
    { threshold: 0.1 }
  )
  stickyObserver.observe(sentinelRef.value)
}

const editingComment = ref(null)   // criterion.id, для которого открыт редактор комментария
const commentDraft = ref('')       // черновик комментария к критерию
const savingItemComment = ref(null)
const editingGeneralComment = ref(false)
const generalCommentDraft = ref('')

onMounted(async () => {
  try {
    logger.log('Загрузка данных оценки', { sheetId: props.sheetId, workId: props.workId })

    // 1. Загружаем лист (для scorecard_id) и работу параллельно
    const [sheetRes, workRes] = await Promise.all([
      api.get('/contest_evaluation_sheets:get', {
        params: { filterByTk: props.sheetId },
      }),
      api.get('/contest_evaluation_sheet_works:get', {
        params: {
          filterByTk: props.workId,
          appends: 'stage_participation,stage_participation.participation',
        },
      }),
    ])
    sheet.value = sheetRes.data.data
    work.value = workRes.data.data
    logger.debug('Лист и работа загружены', { sheet: sheet.value, work: work.value })

    // 2. Критерии + оценка жюри параллельно
    const scorecardId = sheet.value.scorecard_id
    const personId = auth.personId
    logger.debug('personId жюри', personId)

    const round2 = [
      api.get('/contest_scorecard_criteria:list', {
        params: {
          filter: JSON.stringify({ scorecard_id: scorecardId }),
          sort: 'order,id',
          pageSize: 200,
        },
      }),
    ]
    if (personId) {
      round2.push(api.get('/contest_evaluations:list', {
        params: {
          filter: JSON.stringify({
            sheet_work_id: Number(props.workId),
            judge_id: personId,
          }),
          pageSize: 1,
        },
      }))
    }
    const [criteriaRes, evalRes] = await Promise.all(round2)
    criteria.value = criteriaRes.data.data || []
    logger.debug('Критерии загружены', criteria.value.length)

    if (evalRes) {
      evaluation.value = evalRes.data.data?.[0] || null
    }
    if (!evaluation.value) {
      error.value = 'Оценка для данного жюри не найдена'
      logger.warn('Оценка не найдена для жюри')
      loading.value = false
      return
    }
    logger.debug('Evaluation найдена', evaluation.value.id)

    // 3. Категории + уровни + items параллельно
    const categoryIds = [...new Set(criteria.value.map((c) => c.category_id).filter(Boolean))]
    const scaleIds = [...new Set(criteria.value.map((c) => c.scale_id).filter(Boolean))]

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
    parallelRequests.push(api.get('/contest_evaluation_items:list', {
      params: {
        filter: JSON.stringify({ evaluation_id: evaluation.value.id }),
        pageSize: 200,
      },
    }))
    requestKeys.push('items')

    const parallelResults = await Promise.all(parallelRequests)
    const resultMap = {}
    requestKeys.forEach((key, i) => { resultMap[key] = parallelResults[i] })

    if (resultMap.categories) {
      categories.value = resultMap.categories.data.data || []
    }
    if (resultMap.levels) {
      for (const level of resultMap.levels.data.data || []) {
        if (!levelsMap[level.scale_id]) levelsMap[level.scale_id] = []
        levelsMap[level.scale_id].push(level)
      }
    }
    for (const item of resultMap.items.data.data || []) {
      items[item.criterion_id] = item
    }
    logger.log('Данные оценки загружены, items:', Object.keys(items).length)
  } catch (e) {
    logger.error('Ошибка загрузки данных оценки', e)
    error.value = 'Не удалось загрузить данные оценки'
  } finally {
    loading.value = false
    await nextTick()
    initStickyObserver()
  }
})

function getWorkTitle() {
  if (!work.value) return ''
  const sp = work.value.stage_participation
  return sp?.title
    || sp?.participation?.title
    || `Работа #${work.value.id}`
}

function getLevels(criterion) {
  return levelsMap[criterion.scale_id] || []
}

function getSelectedLevel(criterion) {
  return items[criterion.id]?.level_id ?? null
}

const totalScore = computed(() => {
  return criteria.value.reduce((sum, c) => {
    const item = items[c.id]
    return sum + (item?.score ? Number(item.score) : 0)
  }, 0)
})

const hasCategories = computed(() => categories.value.length > 0)

const categoriesMap = computed(() => {
  const map = {}
  for (const cat of categories.value) map[cat.id] = cat
  return map
})

/** Группировка критериев по категориям: [{ category, criteria }]. Без категории — в конце. */
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

function categoryScore(categoryId) {
  return criteria.value
    .filter((c) => c.category_id === categoryId)
    .reduce((sum, c) => sum + (items[c.id]?.score ? Number(items[c.id].score) : 0), 0)
}

/**
 * Выбор уровня оценки для критерия.
 * Применяет оптимистичное обновление UI, затем сохраняет на сервере.
 * При ошибке — откат к предыдущему состоянию.
 * После успешного сохранения синхронизирует итоговый балл на сервере.
 */
async function selectLevel(criterion, level) {
  saving.value = criterion.id
  saved.value = false
  error.value = ''

  const existing = items[criterion.id]
  // Оптимистичное обновление — сразу подсвечиваем выбранный уровень
  const optimistic = {
    ...(existing || {}),
    criterion_id: criterion.id,
    evaluation_id: evaluation.value.id,
    level_id: level.id,
    score: level.point,
  }
  items[criterion.id] = optimistic
  logger.debug('selectLevel — оптимистичное обновление', { criterionId: criterion.id, levelId: level.id })

  try {
    if (existing?.id) {
      // Обновляем существующую запись
      logger.log('Обновление evaluation_item', { id: existing.id, levelId: level.id })
      const { data } = await api.post(
        `/contest_evaluation_items:update?filterByTk=${existing.id}`,
        { level_id: level.id, score: level.point },
      )
      // Мержим ответ с оптимистичными данными
      items[criterion.id] = { ...optimistic, ...data.data }
    } else {
      // Создаём новую запись
      logger.log('Создание evaluation_item', { criterionId: criterion.id, levelId: level.id })
      const { data } = await api.post('/contest_evaluation_items:create', {
        evaluation_id: evaluation.value.id,
        criterion_id: criterion.id,
        level_id: level.id,
        score: level.point,
      })
      items[criterion.id] = { ...optimistic, ...data.data }
    }
    logger.debug('selectLevel — сохранено', items[criterion.id])
    // Автоматически обновляем итог на сервере
    await syncTotalScore()
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка сохранения оценки', e)
    // Откат при ошибке
    if (existing) {
      items[criterion.id] = existing
    } else {
      delete items[criterion.id]
    }
    error.value = 'Ошибка сохранения'
  } finally {
    saving.value = null
  }
}

const savingComment = ref(false)
const resetting = ref(null)

/** Сброс выбранного уровня оценки для критерия */
async function resetLevel(criterion) {
  const existing = items[criterion.id]
  if (!existing?.id) return
  resetting.value = criterion.id
  error.value = ''
  try {
    logger.log('Сброс уровня evaluation_item', { id: existing.id, criterionId: criterion.id })
    const { data } = await api.post(
      `/contest_evaluation_items:update?filterByTk=${existing.id}`,
      { level_id: null, score: null },
    )
    items[criterion.id] = { ...existing, ...data.data, level_id: null, score: null }
    await syncTotalScore()
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка сброса оценки', e)
    items[criterion.id] = existing
    error.value = 'Ошибка сброса оценки'
  } finally {
    resetting.value = null
  }
}

/** Отправка актуального итогового балла на сервер (contest_evaluations:update) */
async function syncTotalScore() {
  if (!evaluation.value) return
  try {
    logger.debug('Синхронизация итога', { evaluationId: evaluation.value.id, score: totalScore.value })
    await api.post(
      `/contest_evaluations:update?filterByTk=${evaluation.value.id}`,
      { score: totalScore.value },
    )
    evaluation.value.score = String(totalScore.value)
  } catch (e) {
    logger.error('Ошибка синхронизации итога', e)
  }
}

function openGeneralComment() {
  editingGeneralComment.value = true
  generalCommentDraft.value = evaluation.value?.comment || ''
}

function cancelGeneralComment() {
  editingGeneralComment.value = false
  generalCommentDraft.value = ''
}

async function saveGeneralComment() {
  if (!evaluation.value) return
  savingComment.value = true
  logger.log('Сохранение общего комментария', { evaluationId: evaluation.value.id })
  try {
    await api.post(
      `/contest_evaluations:update?filterByTk=${evaluation.value.id}`,
      { comment: generalCommentDraft.value },
    )
    evaluation.value.comment = generalCommentDraft.value
    editingGeneralComment.value = false
    generalCommentDraft.value = ''
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка сохранения комментария', e)
    error.value = 'Ошибка сохранения комментария'
  } finally {
    savingComment.value = false
  }
}

function openItemComment(criterion) {
  editingComment.value = criterion.id
  commentDraft.value = items[criterion.id]?.comment || ''
}

function cancelItemComment() {
  editingComment.value = null
  commentDraft.value = ''
}

async function saveItemComment(criterion) {
  const existing = items[criterion.id]
  if (!existing?.id) return
  savingItemComment.value = criterion.id
  logger.log('Сохранение комментария критерия', { itemId: existing.id, criterionId: criterion.id })
  try {
    const { data } = await api.post(
      `/contest_evaluation_items:update?filterByTk=${existing.id}`,
      { comment: commentDraft.value },
    )
    items[criterion.id] = { ...existing, ...data.data, comment: commentDraft.value }
    editingComment.value = null
    commentDraft.value = ''
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка сохранения комментария критерия', e)
    error.value = 'Ошибка сохранения комментария'
  } finally {
    savingItemComment.value = null
  }
}

async function deleteItemComment(criterion) {
  const existing = items[criterion.id]
  if (!existing?.id) return
  savingItemComment.value = criterion.id
  try {
    const { data } = await api.post(
      `/contest_evaluation_items:update?filterByTk=${existing.id}`,
      { comment: null },
    )
    items[criterion.id] = { ...existing, ...data.data, comment: null }
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка удаления комментария критерия', e)
    error.value = 'Ошибка удаления комментария'
  } finally {
    savingItemComment.value = null
  }
}

async function deleteGeneralComment() {
  if (!evaluation.value) return
  savingComment.value = true
  try {
    await api.post(
      `/contest_evaluations:update?filterByTk=${evaluation.value.id}`,
      { comment: null },
    )
    evaluation.value.comment = null
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка удаления общего комментария', e)
    error.value = 'Ошибка удаления комментария'
  } finally {
    savingComment.value = false
  }
}


</script>

<template>
  <div>
    <router-link
      :to="{ name: 'works', params: { sheetId: props.sheetId } }"
      class="mb-4 inline-block text-sm text-primary no-underline hover:underline"
    >
      &larr; К списку работ
    </router-link>

    <div class="mb-2" v-if="work">
      <h1 class="mb-1 text-2xl font-bold text-gray-900 dark:text-gray-100">{{ getWorkTitle() }}</h1>
      <p v-if="sheet?.title" class="text-sm text-gray-500 dark:text-gray-400">{{ sheet.title }}</p>
    </div>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка...</span>
    </div>

    <p v-else-if="error && !criteria.length" class="py-12 text-center text-red-600">{{ error }}</p>

    <template v-else>

      <!-- Criteria list (grouped by categories if available) -->
      <div class="flex flex-col gap-3">
        <template v-for="group in groupedCriteria" :key="group.category?.id ?? 'uncategorized'">
          <!-- Category block wrapper (styled only when categories exist) -->
          <div :class="hasCategories ? 'mt-2 overflow-hidden rounded-xl border border-primary/20' : ''">
            <!-- Category header -->
            <button v-if="hasCategories && group.category" class="flex w-full cursor-pointer items-center justify-between border-none bg-primary/10 px-4 py-2.5 font-sans dark:bg-primary/20" @click="collapsedCategories[group.category.id] = !collapsedCategories[group.category.id]">
              <div class="flex items-center gap-2">
                <svg class="h-4 w-4 text-primary transition-transform" :class="collapsedCategories[group.category.id] ? '' : 'rotate-90'" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
                <h2 class="m-0 text-sm font-bold text-primary">{{ group.category.title }}</h2>
              </div>
              <span class="rounded-full bg-score-light px-3 py-0.5 text-sm font-semibold text-score">{{ categoryScore(group.category.id) }}</span>
            </button>
            <button v-else-if="hasCategories && !group.category" class="flex w-full cursor-pointer items-center justify-between border-none bg-gray-100 px-4 py-2.5 font-sans dark:bg-gray-700/50" @click="collapsedCategories['uncategorized'] = !collapsedCategories['uncategorized']">
              <div class="flex items-center gap-2">
                <svg class="h-4 w-4 text-gray-500 transition-transform" :class="collapsedCategories['uncategorized'] ? '' : 'rotate-90'" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
                <h2 class="m-0 text-sm font-bold text-gray-700 dark:text-gray-200">Без категории</h2>
              </div>
            </button>
            <!-- Criteria inside -->
            <div v-show="!hasCategories || !collapsedCategories[group.category?.id ?? 'uncategorized']" :class="hasCategories ? 'flex flex-col gap-3 p-3' : 'flex flex-col gap-3'">

        <div v-for="criterion in group.criteria" :key="criterion.id" class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <!-- Header -->
          <div class="mb-1 flex items-start justify-between gap-4">
            <h3 class="m-0 text-sm font-semibold text-gray-800 dark:text-gray-200">{{ criterion.title }}</h3>
            <div class="flex shrink-0 items-center gap-2">
              <span class="rounded-full bg-score-light px-2.5 py-0.5 text-sm font-semibold text-score">
                {{ items[criterion.id]?.score ?? '—' }}
              </span>
              <button
                v-if="items[criterion.id]?.id && items[criterion.id]?.level_id != null"
                class="cursor-pointer rounded-md border border-red-200 bg-white px-2 py-0.5 text-xs text-red-600 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:bg-gray-800 dark:hover:bg-red-900/20"
                :disabled="resetting === criterion.id || saving === criterion.id"
                @click.prevent="resetLevel(criterion)"
              >
                {{ resetting === criterion.id ? '...' : 'Удалить оценку' }}
              </button>
            </div>
          </div>
          <p v-if="criterion.description" class="m-0 mb-3 text-xs leading-relaxed text-gray-400 dark:text-gray-500">{{ criterion.description }}</p>
          <div v-else class="mb-2"></div>

          <!-- Level buttons -->
          <div class="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
            <button
              v-for="level in getLevels(criterion)"
              :key="level.id"
              class="flex cursor-pointer flex-col items-center gap-0.5 rounded-lg border-2 bg-white px-3 py-2 transition sm:min-w-12 dark:bg-gray-800"
              :class="[
                getSelectedLevel(criterion) === level.id
                  ? 'border-primary bg-primary! text-white dark:bg-primary!'
                  : 'border-gray-200 hover:border-primary hover:bg-primary-light dark:border-gray-600',
                saving === criterion.id ? 'opacity-60 cursor-wait' : ''
              ]"
              :title="level.title"
              @click="selectLevel(criterion, level)"
              :disabled="saving === criterion.id"
            >
              <span class="text-base font-bold">{{ level.point }}</span>
              <span v-if="level.title" class="text-center text-[11px] leading-tight opacity-80">{{ level.title }}</span>
            </button>
          </div>

          <!-- Criterion comment -->
          <div class="mt-2.5 border-t border-gray-200 pt-2.5 dark:border-gray-700">
            <template v-if="editingComment === criterion.id">
              <textarea
                v-model="commentDraft"
                rows="2"
                placeholder="Комментарий к оценке..."
                class="mb-2 w-full resize-y rounded-md border border-gray-300 bg-gray-50 px-2.5 py-2 font-sans text-sm text-gray-800 transition focus:border-primary focus:ring-2 focus:ring-primary-light focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
              />
              <div class="flex gap-2">
                <button
                  class="cursor-pointer rounded-md bg-primary px-3 py-1 text-sm text-white transition hover:bg-primary-hover disabled:opacity-50"
                  @click="saveItemComment(criterion)"
                  :disabled="savingItemComment === criterion.id"
                >
                  {{ savingItemComment === criterion.id ? 'Сохранение...' : 'Сохранить' }}
                </button>
                <button
                  class="cursor-pointer rounded-md border border-gray-200 bg-white px-3 py-1 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
                  @click="cancelItemComment"
                  :disabled="savingItemComment === criterion.id"
                >
                  Отмена
                </button>
              </div>
            </template>
            <template v-else>
              <p v-if="items[criterion.id]?.comment" class="mb-1.5 whitespace-pre-wrap text-sm text-gray-500 dark:text-gray-400">
                {{ items[criterion.id].comment }}
              </p>
              <div class="flex gap-3">
                <button
                  v-if="items[criterion.id]?.id"
                  class="cursor-pointer border-none bg-transparent p-0 font-sans text-sm text-primary hover:underline"
                  @click="openItemComment(criterion)"
                >
                  {{ items[criterion.id]?.comment ? 'Изменить комментарий' : 'Добавить комментарий' }}
                </button>
                <button
                  v-if="items[criterion.id]?.comment"
                  class="cursor-pointer border-none bg-transparent p-0 font-sans text-sm text-red-500 hover:underline disabled:opacity-50"
                  :disabled="savingItemComment === criterion.id"
                  @click="deleteItemComment(criterion)"
                >
                  Удалить комментарий
                </button>
              </div>
            </template>
          </div>
        </div>
            </div><!-- end criteria list -->
          </div><!-- end category block -->
        </template>
      </div>

      <!-- General comment -->
      <div class="mt-6 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <h3 class="m-0 mb-2 text-sm font-semibold text-gray-800 dark:text-gray-200">Общий комментарий</h3>
        <template v-if="editingGeneralComment">
          <textarea
            v-model="generalCommentDraft"
            rows="3"
            placeholder="Общий комментарий к работе..."
            class="mb-2 w-full resize-y rounded-lg border border-gray-300 bg-gray-50 px-3 py-2.5 font-sans text-sm text-gray-800 transition focus:border-primary focus:ring-2 focus:ring-primary-light focus:outline-none dark:border-gray-600 dark:bg-gray-700 dark:text-gray-200"
          />
          <div class="flex gap-2">
            <button
              class="cursor-pointer rounded-md bg-primary px-3 py-1 text-sm text-white transition hover:bg-primary-hover disabled:opacity-50"
              @click="saveGeneralComment"
              :disabled="savingComment"
            >
              {{ savingComment ? 'Сохранение...' : 'Сохранить' }}
            </button>
            <button
              class="cursor-pointer rounded-md border border-gray-200 bg-white px-3 py-1 text-sm text-gray-700 transition hover:bg-gray-100 disabled:opacity-50 dark:border-gray-600 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600"
              @click="cancelGeneralComment"
              :disabled="savingComment"
            >
              Отмена
            </button>
          </div>
        </template>
        <template v-else>
          <p v-if="evaluation?.comment" class="mb-1.5 whitespace-pre-wrap text-sm text-gray-500 dark:text-gray-400">
            {{ evaluation.comment }}
          </p>
          <div class="flex gap-3">
            <button
              class="cursor-pointer border-none bg-transparent p-0 font-sans text-sm text-primary hover:underline"
              @click="openGeneralComment"
            >
              {{ evaluation?.comment ? 'Изменить комментарий' : 'Добавить комментарий' }}
            </button>
            <button
              v-if="evaluation?.comment"
              class="cursor-pointer border-none bg-transparent p-0 font-sans text-sm text-red-500 hover:underline disabled:opacity-50"
              :disabled="savingComment"
              @click="deleteGeneralComment"
            >
              Удалить комментарий
            </button>
          </div>
        </template>
      </div>

      <p v-if="error" class="mt-4 text-sm text-red-600">{{ error }}</p>

      <!-- Sentinel for sticky detection -->
      <div ref="sentinelRef" class="h-px"></div>
      <!-- Total bar (sticky bottom) -->
      <div
        class="sticky bottom-0 z-30 -mx-4 mt-4 border-t border-score/30 bg-score px-5 py-3 text-white shadow-[0_-4px_12px_rgba(0,0,0,0.15)] transition-[border-radius] duration-200 sm:-mx-6"
        :class="totalBarStuck ? 'rounded-t-xl' : 'rounded-xl'"
      >
        <div class="flex items-center gap-2 text-base">
          <span class="font-medium">Итого:</span>
          <strong class="text-lg">{{ totalScore }}</strong>
          <transition name="fade">
            <span v-if="saved" class="ml-auto text-sm font-medium text-green-200">Сохранено ✓</span>
          </transition>
        </div>
        <div v-if="hasCategories" class="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          <span v-for="group in groupedCriteria" :key="group.category?.id ?? 'uncategorized'" v-show="group.category" class="text-xs text-white/70">
            {{ group.category?.title }}: <strong class="text-white">{{ categoryScore(group.category?.id) }}</strong>
          </span>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
