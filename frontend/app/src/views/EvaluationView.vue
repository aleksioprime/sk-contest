<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
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
const criteria = ref([])
const items = reactive({})      // { [criterion_id]: evaluation_item }
const levelsMap = reactive({})  // { [scale_id]: levels[] }
const loading = ref(true)
const saving = ref(null)
const error = ref('')
const saved = ref(false)
const editingComment = ref(null)   // criterion.id для которого открыт ввод комментария
const commentDraft = ref('')       // черновик комментария критерия
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

    // 2. Загружаем критерии по scorecard_id
    const scorecardId = sheet.value.scorecard_id
    const criteriaRes = await api.get('/contest_scorecard_criteria:list', {
      params: {
        filter: JSON.stringify({ scorecard_id: scorecardId }),
        sort: 'order,id',
        pageSize: 200,
      },
    })
    criteria.value = criteriaRes.data.data || []
    logger.debug('Критерии загружены', criteria.value.length)

    // 3. Загружаем уровни для всех шкал критериев
    const scaleIds = [...new Set(criteria.value.map((c) => c.scale_id).filter(Boolean))]
    if (scaleIds.length) {
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

    // 4. Находим оценку жюри для этой работы
    const personId = auth.personId
    logger.debug('personId жюри', personId)
    if (personId) {
      const evalRes = await api.get('/contest_evaluations:list', {
        params: {
          filter: JSON.stringify({
            sheet_work_id: Number(props.workId),
            judge_id: personId,
          }),
          pageSize: 1,
        },
      })
      evaluation.value = evalRes.data.data?.[0] || null
    }

    if (!evaluation.value) {
      error.value = 'Оценка для данного жюри не найдена'
      logger.warn('Оценка не найдена для жюри')
      loading.value = false
      return
    }
    logger.debug('Evaluation найдена', evaluation.value.id)

    // 5. Загружаем существующие evaluation_items
    const itemsRes = await api.get('/contest_evaluation_items:list', {
      params: {
        filter: JSON.stringify({ evaluation_id: evaluation.value.id }),
        pageSize: 200,
      },
    })
    for (const item of itemsRes.data.data || []) {
      items[item.criterion_id] = item
    }
    logger.log('Данные оценки загружены, items:', Object.keys(items).length)
  } catch (e) {
    logger.error('Ошибка загрузки данных оценки', e)
    error.value = 'Не удалось загрузить данные оценки'
  } finally {
    loading.value = false
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
      <!-- Total bar -->
      <div class="sticky top-14 z-5 mb-5 flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-5 py-3.5 text-base dark:border-gray-700 dark:bg-gray-800">
        <span>Итого:</span>
        <strong>{{ totalScore }}</strong>
        <transition name="fade">
          <span v-if="saved" class="ml-auto text-sm font-medium text-green-600">Сохранено</span>
        </transition>
      </div>

      <!-- Criteria list -->
      <div class="flex flex-col gap-3">
        <div v-for="criterion in criteria" :key="criterion.id" class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
          <!-- Header -->
          <div class="mb-3 flex items-start justify-between gap-4">
            <h3 class="m-0 text-sm font-semibold text-gray-800 dark:text-gray-200">{{ criterion.title }}</h3>
            <div class="flex shrink-0 items-center gap-2">
              <span class="rounded-full bg-primary-light px-2.5 py-0.5 text-sm font-semibold text-primary">
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

          <!-- Level buttons -->
          <div class="flex flex-wrap gap-2">
            <button
              v-for="level in getLevels(criterion)"
              :key="level.id"
              class="flex min-w-12 cursor-pointer flex-col items-center gap-0.5 rounded-lg border-2 bg-white px-3 py-2 transition dark:bg-gray-800"
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
              <span v-if="level.title" class="max-w-20 truncate text-center text-[11px] opacity-80">{{ level.title }}</span>
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
