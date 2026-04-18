<script setup>
import { ref, reactive, computed, onMounted, nextTick, watch } from 'vue'
import publicApi from '../api/public'

const props = defineProps({
  token: { type: String, required: true },
})

const sheet = ref(null)
const work = ref(null)
const evaluation = ref(null)
const criteria = ref([])
const categories = ref([])
const items = reactive({})
const levelsMap = reactive({})

const loading = ref(true)
const error = ref('')
const fatalState = ref(null)
const saving = ref(null)
const resetting = ref(null)
const saved = ref(false)

const collapsedCategories = reactive({})

const editingComment = ref(null)
const commentDraft = ref('')
const savingItemComment = ref(null)

const editingGeneralComment = ref(false)
const generalCommentDraft = ref('')
const savingComment = ref(false)

function setSaved() {
  saved.value = true
  setTimeout(() => {
    saved.value = false
  }, 1500)
}

function resolveFatalState(requestError) {
  const status = requestError?.response?.status
  const detail = requestError?.response?.data?.detail

  if (status === 404) {
    return {
      title: 'Ссылка недействительна',
      description: 'Проверьте адрес ссылки или запросите новую ссылку для оценки.',
    }
  }

  if (status === 403) {
    return {
      title: 'Лист закрыт для оценки',
      description: typeof detail === 'string' && detail
        ? detail
        : 'Этот оценочный лист сейчас недоступен для анонимной оценки.',
    }
  }

  return {
    title: 'Не удалось открыть страницу',
    description: typeof detail === 'string' && detail
      ? detail
      : 'Произошла ошибка загрузки. Попробуйте обновить страницу позже.',
  }
}

function resetData() {
  sheet.value = null
  work.value = null
  evaluation.value = null
  criteria.value = []
  categories.value = []
  error.value = ''
  fatalState.value = null

  Object.keys(items).forEach((key) => delete items[key])
  Object.keys(levelsMap).forEach((key) => delete levelsMap[key])
}

function applyBundle(bundle) {
  resetData()

  sheet.value = bundle.sheet || null
  work.value = bundle.work || null
  evaluation.value = bundle.evaluation || null
  criteria.value = bundle.criteria || []
  categories.value = bundle.categories || []

  for (const level of bundle.levels || []) {
    if (!levelsMap[level.scale_id]) levelsMap[level.scale_id] = []
    levelsMap[level.scale_id].push(level)
  }

  for (const item of bundle.items || []) {
    items[item.criterion_id] = item
  }
}

async function loadBundle() {
  loading.value = true
  error.value = ''
  fatalState.value = null
  resetData()

  try {
    const { data } = await publicApi.get(`/public/evaluations/${props.token}`)
    applyBundle(data)
  } catch (e) {
    fatalState.value = resolveFatalState(e)
  } finally {
    loading.value = false
    await nextTick()
  }
}

onMounted(loadBundle)
watch(() => props.token, loadBundle)

function getWorkTitle() {
  if (!work.value) return ''
  const sp = work.value.stage_participation
  return sp?.title || sp?.participation?.title || `Работа #${work.value.id}`
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

function getLevels(criterion) {
  return levelsMap[criterion.scale_id] || []
}

function getSelectedLevel(criterion) {
  return items[criterion.id]?.level_id ?? null
}

const totalScore = computed(() => {
  return criteria.value.reduce((sum, criterion) => {
    const item = items[criterion.id]
    return sum + (item?.score ? Number(item.score) : 0)
  }, 0)
})

const allCriteriaScored = computed(() => {
  if (!criteria.value.length) return false
  return criteria.value.every((criterion) => items[criterion.id]?.level_id != null)
})

const hasCategories = computed(() => categories.value.length > 0)

const categoriesMap = computed(() => {
  const map = {}
  for (const category of categories.value) {
    map[category.id] = category
  }
  return map
})

const groupedCriteria = computed(() => {
  if (!hasCategories.value) return [{ category: null, criteria: criteria.value }]

  const groups = {}
  const uncategorized = []

  for (const criterion of criteria.value) {
    if (criterion.category_id && categoriesMap.value[criterion.category_id]) {
      if (!groups[criterion.category_id]) groups[criterion.category_id] = []
      groups[criterion.category_id].push(criterion)
    } else {
      uncategorized.push(criterion)
    }
  }

  const result = categories.value
    .filter((category) => groups[category.id])
    .map((category) => ({ category, criteria: groups[category.id] }))

  if (uncategorized.length) result.push({ category: null, criteria: uncategorized })
  return result
})

function categoryScore(categoryId) {
  return criteria.value
    .filter((criterion) => criterion.category_id === categoryId)
    .reduce((sum, criterion) => sum + (items[criterion.id]?.score ? Number(items[criterion.id].score) : 0), 0)
}

async function selectLevel(criterion, level) {
  saving.value = criterion.id
  error.value = ''

  const existing = items[criterion.id]
  const optimistic = {
    ...(existing || {}),
    criterion_id: criterion.id,
    evaluation_id: evaluation.value?.id,
    level_id: level.id,
    score: level.point,
  }

  items[criterion.id] = optimistic

  try {
    const { data } = await publicApi.patch(
      `/public/evaluations/${props.token}/criteria/${criterion.id}/level`,
      { level_id: level.id },
    )

    items[criterion.id] = { ...optimistic, ...(data.item || {}) }
    if (data.evaluation) evaluation.value = { ...(evaluation.value || {}), ...data.evaluation }
    setSaved()
  } catch (e) {
    if (existing) {
      items[criterion.id] = existing
    } else {
      delete items[criterion.id]
    }
    error.value = e?.response?.data?.detail || 'Ошибка сохранения оценки'
  } finally {
    saving.value = null
  }
}

async function resetLevel(criterion) {
  const existing = items[criterion.id]
  if (!existing?.id) return

  resetting.value = criterion.id
  error.value = ''

  try {
    const { data } = await publicApi.patch(
      `/public/evaluations/${props.token}/criteria/${criterion.id}/level`,
      { level_id: null },
    )

    items[criterion.id] = {
      ...existing,
      ...(data.item || {}),
      level_id: null,
      score: null,
    }
    if (data.evaluation) evaluation.value = { ...(evaluation.value || {}), ...data.evaluation }
    setSaved()
  } catch (e) {
    items[criterion.id] = existing
    error.value = e?.response?.data?.detail || 'Ошибка сброса оценки'
  } finally {
    resetting.value = null
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
  error.value = ''

  try {
    const { data } = await publicApi.patch(
      `/public/evaluations/${props.token}/criteria/${criterion.id}/comment`,
      { comment: commentDraft.value || null },
    )

    items[criterion.id] = {
      ...existing,
      ...(data.item || {}),
      comment: commentDraft.value || null,
    }

    editingComment.value = null
    commentDraft.value = ''
    setSaved()
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Ошибка сохранения комментария'
  } finally {
    savingItemComment.value = null
  }
}

async function deleteItemComment(criterion) {
  const existing = items[criterion.id]
  if (!existing?.id) return

  savingItemComment.value = criterion.id
  error.value = ''

  try {
    const { data } = await publicApi.patch(
      `/public/evaluations/${props.token}/criteria/${criterion.id}/comment`,
      { comment: null },
    )

    items[criterion.id] = {
      ...existing,
      ...(data.item || {}),
      comment: null,
    }

    setSaved()
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Ошибка удаления комментария'
  } finally {
    savingItemComment.value = null
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
  error.value = ''

  try {
    const { data } = await publicApi.patch(`/public/evaluations/${props.token}/comment`, {
      comment: generalCommentDraft.value || null,
    })

    evaluation.value = {
      ...(evaluation.value || {}),
      ...(data.evaluation || {}),
      comment: generalCommentDraft.value || null,
    }

    editingGeneralComment.value = false
    generalCommentDraft.value = ''
    setSaved()
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Ошибка сохранения комментария'
  } finally {
    savingComment.value = false
  }
}

async function deleteGeneralComment() {
  if (!evaluation.value) return

  savingComment.value = true
  error.value = ''

  try {
    const { data } = await publicApi.patch(`/public/evaluations/${props.token}/comment`, {
      comment: null,
    })

    evaluation.value = {
      ...(evaluation.value || {}),
      ...(data.evaluation || {}),
      comment: null,
    }

    setSaved()
  } catch (e) {
    error.value = e?.response?.data?.detail || 'Ошибка удаления комментария'
  } finally {
    savingComment.value = false
  }
}
</script>

<template>
  <div>
    <div class="mb-2" v-if="work">
      <div class="mb-1 flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <div class="mb-1 flex flex-wrap items-center gap-2">
            <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">{{ getWorkTitle() }}</h1>
            <span
              v-if="isExternalWork()"
              class="inline-block rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
            >
              Внешний участник
            </span>
          </div>
          <p v-if="sheet?.title" class="text-sm text-gray-500 dark:text-gray-400">{{ sheet.title }}</p>
        </div>
        <span
          class="shrink-0 rounded-full px-3 py-1 text-xs font-semibold"
          :class="allCriteriaScored
            ? 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300'
            : 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300'"
        >
          {{ allCriteriaScored ? 'Все оценки выставлены' : 'Не все оценки выставлены' }}
        </span>
      </div>
      <div v-if="getParticipants().length" class="mt-1 text-sm text-gray-600 dark:text-gray-400">
        <span class="font-medium">Участники:</span> {{ getParticipantsLabel() }}
      </div>
      <div v-if="getSupervisors().length" class="mt-0.5 text-sm text-gray-500 dark:text-gray-400">
        <span class="font-medium">Руководители:</span> {{ getSupervisorsLabel() }}
      </div>
      <div v-if="getWorkNotes()" class="mt-1 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-900/20 dark:text-blue-100">
        <span class="font-medium">Примечание:</span> {{ getWorkNotes() }}
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center gap-3 py-12 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка...</span>
    </div>

    <div v-else-if="fatalState" class="mx-auto flex min-h-[60vh] max-w-2xl items-center justify-center">
      <div class="w-full rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center shadow-sm dark:border-amber-900/50 dark:bg-amber-900/20">
        <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-300">
          <svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" viewBox="0 0 20 20" fill="currentColor">
            <path fill-rule="evenodd" d="M8.257 3.099c.765-1.36 2.72-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.981-1.742 2.981H4.42c-1.53 0-2.492-1.647-1.742-2.98l5.58-9.921ZM11 13a1 1 0 1 0-2 0 1 1 0 0 0 2 0Zm-1-7a1 1 0 0 0-1 1v3a1 1 0 1 0 2 0V7a1 1 0 0 0-1-1Z" clip-rule="evenodd" />
          </svg>
        </div>
        <h2 class="mb-2 text-xl font-semibold text-amber-900 dark:text-amber-200">{{ fatalState.title }}</h2>
        <p class="mx-auto mb-6 max-w-xl text-sm leading-relaxed text-amber-800 dark:text-amber-300">{{ fatalState.description }}</p>
        <button
          class="inline-flex cursor-pointer items-center rounded-lg border border-amber-300 bg-white px-4 py-2 text-sm font-medium text-amber-700 transition hover:bg-amber-100 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-300 dark:hover:bg-amber-900/40"
          @click="loadBundle"
        >
          Попробовать снова
        </button>
      </div>
    </div>

    <template v-else>
      <div class="flex flex-col gap-3">
        <template v-for="group in groupedCriteria" :key="group.category?.id ?? 'uncategorized'">
          <div :class="hasCategories ? 'mt-2 overflow-hidden rounded-xl border border-primary/20' : ''">
            <button v-if="hasCategories && group.category" class="flex w-full cursor-pointer items-center justify-between border-none bg-primary/10 px-4 py-2.5 font-sans dark:bg-primary/20" @click="collapsedCategories[group.category.id] = !collapsedCategories[group.category.id]">
              <div class="flex items-center gap-2">
                <svg class="h-4 w-4 text-primary transition-transform" :class="collapsedCategories[group.category.id] ? '' : 'rotate-90'" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
                <h2 class="m-0 text-sm font-bold text-primary">{{ group.category.title }}</h2>
              </div>
              <span class="rounded-full bg-score-light px-3 py-0.5 text-sm font-semibold text-score">{{ categoryScore(group.category.id) }}</span>
            </button>
            <button v-else-if="hasCategories && !group.category" class="flex w-full cursor-pointer items-center justify-between border-none bg-gray-100 px-4 py-2.5 font-sans dark:bg-gray-700/50" @click="collapsedCategories.uncategorized = !collapsedCategories.uncategorized">
              <div class="flex items-center gap-2">
                <svg class="h-4 w-4 text-gray-500 transition-transform" :class="collapsedCategories.uncategorized ? '' : 'rotate-90'" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M7.21 14.77a.75.75 0 01.02-1.06L11.168 10 7.23 6.29a.75.75 0 111.04-1.08l4.5 4.25a.75.75 0 010 1.08l-4.5 4.25a.75.75 0 01-1.06-.02z" clip-rule="evenodd" /></svg>
                <h2 class="m-0 text-sm font-bold text-gray-700 dark:text-gray-200">Без категории</h2>
              </div>
            </button>

            <div v-show="!hasCategories || !collapsedCategories[group.category?.id ?? 'uncategorized']" :class="hasCategories ? 'flex flex-col gap-3 p-3' : 'flex flex-col gap-3'">
              <div v-for="criterion in group.criteria" :key="criterion.id" class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
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

                <div class="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
                  <button
                    v-for="level in getLevels(criterion)"
                    :key="level.id"
                    class="flex cursor-pointer flex-col items-center gap-0.5 rounded-lg border-2 bg-white px-3 py-2 transition sm:min-w-12 dark:bg-gray-800"
                    :class="[
                      getSelectedLevel(criterion) === level.id
                        ? 'border-primary bg-primary! text-white dark:bg-primary!'
                        : 'border-gray-200 hover:border-primary hover:bg-primary-light dark:border-gray-600',
                      saving === criterion.id ? 'cursor-wait opacity-60' : ''
                    ]"
                    :title="level.title"
                    @click="selectLevel(criterion, level)"
                    :disabled="saving === criterion.id"
                  >
                    <span class="text-base font-bold">{{ level.point }}</span>
                    <span v-if="level.title" class="text-center text-[11px] leading-tight opacity-80">{{ level.title }}</span>
                  </button>
                </div>

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
          </div>
        </template>
      </div>

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

      <div
        class="sticky bottom-0 z-30 -mx-4 mt-4 rounded-t-xl border-t px-5 py-3 text-white shadow-[0_-4px_12px_rgba(0,0,0,0.15)] transition-[background-color,border-color] duration-200 sm:-mx-6"
        :class="allCriteriaScored ? 'border-green-500/40 bg-green-600' : 'border-score/30 bg-score'"
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
