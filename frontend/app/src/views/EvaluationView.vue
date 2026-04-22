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
const checklistOptionsMap = reactive({}) // { criterion_id: options[] } — пункты чеклиста
const checklistSelectedOptionIds = reactive({}) // { criterion_id: option_id[] } — выбранные пункты
const checklistSelectionIdsMap = reactive({}) // { criterion_id: { option_id: selection_id } } — строки связки item_option
const loading = ref(true)
const saving = ref(null)
const error = ref('')
const saved = ref(false)
const collapsedCategories = reactive({}) // { categoryKey: true } — свёрнутые категории
const totalBarStuck = ref(false)         // true, когда панель итогов «прилипла» к низу экрана
const sentinelRef = ref(null)            // ref-элемент для IntersectionObserver
let stickyObserver = null
const showScrollTop = ref(false)

function handleScroll() {
  showScrollTop.value = window.scrollY > 400
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

onUnmounted(() => {
  if (stickyObserver) stickyObserver.disconnect()
  window.removeEventListener('scroll', handleScroll)
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
const hasPendingWrites = computed(() => (
  saving.value != null
  || resetting.value != null
  || savingComment.value
  || savingItemComment.value != null
))

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
          appends: 'participation,participation.participants,participation.supervisors',
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

    // 3. Категории + уровни + items + checklist options
    const categoryIds = [...new Set(criteria.value.map((c) => c.category_id).filter(Boolean))]
    const scaleIds = [...new Set(criteria.value.map((c) => c.scale_id).filter(Boolean))]
    const checklistCriterionIds = criteria.value
      .filter((criterion) => isChecklistCriterion(criterion))
      .map((criterion) => Number(criterion.id))
      .filter(Boolean)

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
    if (checklistCriterionIds.length) {
      parallelRequests.push(api.get('/contest_scorecard_criterion_options:list', {
        params: {
          filter: JSON.stringify({ criterion_id: { $in: checklistCriterionIds } }),
          sort: 'order,id',
          pageSize: 2000,
        },
      }))
      requestKeys.push('checklistOptions')
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
    resetChecklistState()
    const itemCriterionMap = {}
    for (const item of resultMap.items.data.data || []) {
      items[item.criterion_id] = item
      if (item?.id != null) itemCriterionMap[Number(item.id)] = Number(item.criterion_id)
    }
    if (resultMap.checklistOptions) {
      for (const option of resultMap.checklistOptions.data.data || []) {
        const criterionId = Number(option?.criterion_id)
        if (!criterionId) continue
        if (!checklistOptionsMap[criterionId]) checklistOptionsMap[criterionId] = []
        checklistOptionsMap[criterionId].push(option)
      }
    }

    const evaluationItemIds = Object.keys(itemCriterionMap).map((id) => Number(id)).filter(Boolean)
    if (evaluationItemIds.length && checklistCriterionIds.length) {
      let relationData = null
      try {
        const { data } = await api.get('/contest_evaluation_item_options:list', {
          params: {
            filter: JSON.stringify({ evaluation_item_id: { $in: evaluationItemIds } }),
            pageSize: 5000,
          },
        })
        relationData = data
      } catch (firstError) {
        const { data } = await api.get('/contest_evaluation_item_options:list', {
          params: {
            filter: JSON.stringify({ evaluation_item: { $in: evaluationItemIds } }),
            pageSize: 5000,
          },
        })
        relationData = data
      }
      for (const relation of relationData.data || []) {
        const evaluationItemId = getChecklistRelationEvaluationItemId(relation)
        const criterionId = itemCriterionMap[evaluationItemId]
        const optionId = getChecklistRelationOptionId(relation)
        const relationId = relation?.id != null ? Number(relation.id) : null
        if (!criterionId || !optionId) continue
        ensureChecklistCriterionState(criterionId)
        if (!checklistSelectedOptionIds[criterionId].includes(optionId)) {
          checklistSelectedOptionIds[criterionId].push(optionId)
        }
        if (relationId != null) {
          checklistSelectionIdsMap[criterionId][optionId] = relationId
        }
      }
    }

    for (const criterion of criteria.value) {
      if (isChecklistCriterion(criterion)) {
        recalcChecklistCriterionScore(criterion.id)
      }
    }
    logger.log('Данные оценки загружены, items:', Object.keys(items).length)
  } catch (e) {
    logger.error('Ошибка загрузки данных оценки', e)
    error.value = 'Не удалось загрузить данные оценки'
  } finally {
    loading.value = false
    await nextTick()
    initStickyObserver()
    window.addEventListener('scroll', handleScroll)
  }
})

function getWorkTitle() {
  if (!work.value) return ''
  const participation = getParticipation()
  return participation?.title
    || work.value?.stage_participation?.title
    || `Работа #${work.value.id}`
}

function getParticipation() {
  return work.value?.participation || work.value?.stage_participation?.participation || null
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

function getChecklistOptions(criterion) {
  return checklistOptionsMap[Number(criterion?.id)] || []
}

function getSelectedLevel(criterion) {
  return items[criterion.id]?.level_id ?? null
}

function isChecklistCriterion(criterion) {
  return String(criterion?.type || 'scale') === 'checklist'
}

function ensureChecklistCriterionState(criterionId) {
  const key = Number(criterionId)
  if (!checklistSelectedOptionIds[key]) checklistSelectedOptionIds[key] = []
  if (!checklistSelectionIdsMap[key]) checklistSelectionIdsMap[key] = {}
}

function resetChecklistState() {
  for (const key of Object.keys(checklistOptionsMap)) delete checklistOptionsMap[key]
  for (const key of Object.keys(checklistSelectedOptionIds)) delete checklistSelectedOptionIds[key]
  for (const key of Object.keys(checklistSelectionIdsMap)) delete checklistSelectionIdsMap[key]
}

function getChecklistRelationOptionId(relation) {
  const value = relation?.option_id ?? relation?.item_id ?? relation?.option?.id ?? relation?.item?.id
  const id = Number(value)
  return Number.isNaN(id) ? null : id
}

function getChecklistRelationEvaluationItemId(relation) {
  const value = relation?.evaluation_item_id ?? relation?.evaluation_item?.id ?? relation?.evaluation_item
  const id = Number(value)
  return Number.isNaN(id) ? null : id
}

function getChecklistOptionPoint(option) {
  const point = Number(option?.point ?? option?.score ?? 0)
  return Number.isNaN(point) ? 0 : point
}

function formatChecklistOptionPoint(value) {
  const point = getChecklistOptionPoint({ point: value })
  return Number.isInteger(point) ? String(point) : point.toFixed(2)
}

function isTruthyFlag(value) {
  if (value === true || value === 1) return true
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    return normalized === '1' || normalized === 'true' || normalized === 'yes'
  }
  return false
}

function isChecklistOptionExclusive(option) {
  return isTruthyFlag(option?.is_exclusive)
}

function getChecklistOptionById(criterionId, optionId) {
  const options = checklistOptionsMap[Number(criterionId)] || []
  return options.find((entry) => Number(entry?.id) === Number(optionId)) || null
}

function recalcChecklistCriterionScore(criterionId) {
  const key = Number(criterionId)
  const item = items[key]
  if (!item) return
  const selectedIds = checklistSelectedOptionIds[key] || []
  const options = checklistOptionsMap[key] || []
  if (!selectedIds.length) {
    item.score = null
    item.level_id = null
    return
  }
  const selectedSet = new Set(selectedIds.map((id) => Number(id)))
  const sum = options.reduce((acc, option) => {
    const optionId = Number(option?.id)
    if (!selectedSet.has(optionId)) return acc
    return acc + getChecklistOptionPoint(option)
  }, 0)
  item.score = Number(sum.toFixed(2))
  item.level_id = null
}

function isChecklistOptionSelected(criterion, option) {
  const criterionId = Number(criterion?.id)
  const optionId = Number(option?.id)
  return (checklistSelectedOptionIds[criterionId] || []).includes(optionId)
}

function isCriterionScored(criterion) {
  if (isChecklistCriterion(criterion)) {
    return (checklistSelectedOptionIds[Number(criterion.id)] || []).length > 0
  }
  return items[criterion.id]?.level_id != null
}

const totalScore = computed(() => {
  return criteria.value.reduce((sum, c) => {
    const item = items[c.id]
    return sum + (item?.score != null ? Number(item.score) : 0)
  }, 0)
})

const allCriteriaScored = computed(() => {
  if (!criteria.value.length) return false
  return criteria.value.every((criterion) => isCriterionScored(criterion))
})
const scoredCriteriaCount = computed(() => {
  return criteria.value.filter((criterion) => isCriterionScored(criterion)).length
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
    .reduce((sum, c) => sum + (items[c.id]?.score != null ? Number(items[c.id].score) : 0), 0)
}

function getChecklistSelectedCount(criterion) {
  return (checklistSelectedOptionIds[Number(criterion?.id)] || []).length
}

function hasChecklistExclusiveSelected(criterion) {
  const criterionId = Number(criterion?.id)
  if (!criterionId) return false
  const selectedIds = checklistSelectedOptionIds[criterionId] || []
  return selectedIds.some((id) => (
    isChecklistOptionExclusive(getChecklistOptionById(criterionId, id))
  ))
}

/**
 * Выбор уровня оценки для критерия.
 * Применяет оптимистичное обновление UI, затем сохраняет на сервере.
 * При ошибке — откат к предыдущему состоянию.
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
    await refreshCriterionItemFromBackend(criterion.id)
    logger.debug('selectLevel — сохранено', items[criterion.id])
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

async function refreshCriterionItemFromBackend(criterionId) {
  const key = Number(criterionId)
  const currentItem = items[key]
  if (!currentItem?.id) return
  try {
    const { data } = await api.get('/contest_evaluation_items:get', {
      params: { filterByTk: currentItem.id },
    })
    const backendItem = data?.data
    if (backendItem?.id != null) {
      items[key] = { ...(items[key] || {}), ...backendItem }
    }
  } catch (e) {
    logger.warn('Не удалось обновить evaluation_item после сохранения', { criterionId: key, error: e?.message })
  }
}

async function ensureEvaluationItem(criterion) {
  const existing = items[criterion.id]
  if (existing?.id) return existing

  const { data } = await api.post('/contest_evaluation_items:create', {
    evaluation_id: evaluation.value.id,
    criterion_id: criterion.id,
    level_id: null,
    score: null,
  })
  const created = { criterion_id: criterion.id, evaluation_id: evaluation.value.id, ...(data.data || {}) }
  items[criterion.id] = created
  return created
}

async function createChecklistRelationRow(evaluationItemId, optionId) {
  const { data } = await api.post('/contest_evaluation_item_options:create', {
    evaluation_item: evaluationItemId,
    option: optionId,
  })
  return data.data || {}
}

async function deleteChecklistRelationRow(relationId) {
  await api.post(`/contest_evaluation_item_options:destroy?filterByTk=${relationId}`)
}

async function bulkDeleteChecklistRelationRows(relationIds) {
  const ids = relationIds.map((id) => Number(id)).filter(Boolean)
  if (!ids.length) return
  await api.post('/contest_evaluation_item_options:destroy', {}, {
    params: {
      filter: JSON.stringify({ id: { $in: ids } }),
    },
  })
}

async function toggleChecklistOption(criterion, option) {
  const criterionId = Number(criterion?.id)
  const optionId = Number(option?.id)
  if (!criterionId || !optionId || !evaluation.value?.id) return

  saving.value = criterionId
  saved.value = false
  error.value = ''

  ensureChecklistCriterionState(criterionId)
  const selected = checklistSelectedOptionIds[criterionId]
  const selectionMap = checklistSelectionIdsMap[criterionId]
  const wasSelected = selected.includes(optionId)
  const prevSelected = [...selected]
  const prevSelectionMap = { ...selectionMap }
  const prevItem = items[criterionId] ? { ...items[criterionId] } : null

  try {
    const item = await ensureEvaluationItem(criterion)

    if (wasSelected) {
      const relationId = selectionMap[optionId]
      if (relationId == null) throw new Error('Checklist relation id is missing')
      checklistSelectedOptionIds[criterionId] = selected.filter((id) => Number(id) !== optionId)
      delete checklistSelectionIdsMap[criterionId][optionId]
      await deleteChecklistRelationRow(relationId)
    } else {
      const selectingExclusive = isChecklistOptionExclusive(option)
      const selectedExclusiveIds = selected.filter((id) => (
        isChecklistOptionExclusive(getChecklistOptionById(criterionId, id))
      ))
      const idsToDrop = selectingExclusive ? [...selected] : selectedExclusiveIds

      if (idsToDrop.length) {
        const relationIdsToDrop = idsToDrop
          .map((id) => selectionMap[id])
          .filter((id) => id != null)
        if (relationIdsToDrop.length !== idsToDrop.length) {
          throw new Error('Checklist relation id is missing for exclusive cleanup')
        }
        await bulkDeleteChecklistRelationRows(relationIdsToDrop)
        const idsToDropSet = new Set(idsToDrop.map((id) => Number(id)))
        checklistSelectedOptionIds[criterionId] = selected.filter((id) => !idsToDropSet.has(Number(id)))
        const nextSelectionMap = {}
        for (const id of checklistSelectedOptionIds[criterionId]) {
          const relationId = selectionMap[id]
          if (relationId != null) nextSelectionMap[id] = relationId
        }
        checklistSelectionIdsMap[criterionId] = nextSelectionMap
      }

      const created = await createChecklistRelationRow(item.id, optionId)
      const createdId = created?.id != null ? Number(created.id) : null
      checklistSelectedOptionIds[criterionId] = [...checklistSelectedOptionIds[criterionId], optionId]
      if (createdId != null && !Number.isNaN(createdId)) {
        checklistSelectionIdsMap[criterionId][optionId] = createdId
      }
    }

    recalcChecklistCriterionScore(criterionId)
    await refreshCriterionItemFromBackend(criterionId)

    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка изменения чеклиста', e)
    checklistSelectedOptionIds[criterionId] = prevSelected
    checklistSelectionIdsMap[criterionId] = prevSelectionMap
    if (prevItem) {
      items[criterionId] = prevItem
    } else {
      delete items[criterionId]
    }
    error.value = 'Ошибка сохранения'
  } finally {
    saving.value = null
  }
}

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
    await refreshCriterionItemFromBackend(criterion.id)
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

async function clearChecklist(criterion) {
  const criterionId = Number(criterion?.id)
  if (!criterionId) return
  const selectedIds = [...(checklistSelectedOptionIds[criterionId] || [])]
  if (!selectedIds.length) return

  saving.value = criterionId
  saved.value = false
  error.value = ''

  const prevSelected = [...selectedIds]
  const prevSelectionMap = { ...(checklistSelectionIdsMap[criterionId] || {}) }
  const prevItem = items[criterionId] ? { ...items[criterionId] } : null

  try {
    const relationIds = selectedIds
      .map((optionId) => checklistSelectionIdsMap[criterionId]?.[optionId])
      .filter((id) => id != null)
    await bulkDeleteChecklistRelationRows(relationIds)

    checklistSelectedOptionIds[criterionId] = []
    checklistSelectionIdsMap[criterionId] = {}
    recalcChecklistCriterionScore(criterionId)
    await refreshCriterionItemFromBackend(criterionId)
    saved.value = true
    setTimeout(() => { saved.value = false }, 1500)
  } catch (e) {
    logger.error('Ошибка очистки чеклиста', e)
    checklistSelectedOptionIds[criterionId] = prevSelected
    checklistSelectionIdsMap[criterionId] = prevSelectionMap
    if (prevItem) {
      items[criterionId] = prevItem
    } else {
      delete items[criterionId]
    }
    error.value = 'Ошибка сброса оценки'
  } finally {
    saving.value = null
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

    <div class="my-5" v-if="work">
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
      <div class="mt-3 space-y-1.5">
        <div v-if="getParticipants().length" class="text-sm text-gray-600 dark:text-gray-400">
          <span class="font-medium">Участники:</span> {{ getParticipantsLabel() }}
        </div>
        <div v-if="getSupervisors().length" class="text-sm text-gray-500 dark:text-gray-400">
          <span class="font-medium">Руководители:</span> {{ getSupervisorsLabel() }}
        </div>
        <div v-if="getWorkNotes()" class="rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-900 dark:border-blue-900/50 dark:bg-blue-900/20 dark:text-blue-100">
          <span class="font-medium">Примечание:</span> {{ getWorkNotes() }}
        </div>
      </div>
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

        <div
          v-for="criterion in group.criteria"
          :key="criterion.id"
          class="rounded-2xl border border-gray-200/90 bg-white px-4 py-4 shadow-sm transition-colors dark:border-gray-700 dark:bg-gray-800 sm:px-5 sm:py-5"
        >
          <!-- Header -->
          <div class="mb-2 flex flex-wrap items-start justify-between gap-3">
            <div class="min-w-0">
              <h3 class="m-0 text-base font-semibold leading-tight text-gray-800 dark:text-gray-100">{{ criterion.title }}</h3>
              <p v-if="criterion.description" class="m-0 mt-1 text-xs leading-relaxed text-gray-500 dark:text-gray-400">
                {{ criterion.description }}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <span class="rounded-full bg-score-light px-3 py-1 text-sm font-semibold text-score">
                {{ items[criterion.id]?.score ?? '—' }}
              </span>
              <span
                v-if="isChecklistCriterion(criterion)"
                class="rounded-full bg-gray-100 px-2.5 py-1 text-xs font-semibold text-gray-600 dark:bg-gray-700 dark:text-gray-300"
              >
                Выбрано: {{ getChecklistSelectedCount(criterion) }}
              </span>
              <button
                v-if="!isChecklistCriterion(criterion) && items[criterion.id]?.id && items[criterion.id]?.level_id != null"
                class="min-h-9 cursor-pointer rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:bg-gray-800 dark:hover:bg-red-900/20"
                :disabled="resetting === criterion.id || saving === criterion.id"
                @click.prevent="resetLevel(criterion)"
              >
                {{ resetting === criterion.id ? '...' : 'Удалить оценку' }}
              </button>
              <button
                v-if="isChecklistCriterion(criterion) && (checklistSelectedOptionIds[Number(criterion.id)] || []).length"
                class="min-h-9 cursor-pointer rounded-lg border border-red-200 bg-white px-2.5 py-1 text-xs font-medium text-red-600 transition hover:bg-red-50 disabled:opacity-50 dark:border-red-800 dark:bg-gray-800 dark:hover:bg-red-900/20"
                :disabled="saving === criterion.id"
                @click.prevent="clearChecklist(criterion)"
              >
                {{ saving === criterion.id ? '...' : 'Очистить выбор' }}
              </button>
            </div>
          </div>

          <!-- Scale buttons -->
          <div v-if="!isChecklistCriterion(criterion)" class="grid grid-cols-3 gap-2 sm:flex sm:flex-wrap">
            <button
              v-for="level in getLevels(criterion)"
              :key="level.id"
              class="min-h-14 touch-manipulation flex cursor-pointer flex-col items-center justify-center gap-0.5 rounded-xl border-2 bg-white px-3 py-2.5 transition sm:min-w-16 dark:bg-gray-800"
              :class="[
                getSelectedLevel(criterion) === level.id
                  ? 'border-primary bg-primary! text-white shadow-sm dark:bg-primary!'
                  : 'border-gray-200 hover:border-primary hover:bg-primary-light/60 dark:border-gray-600',
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
          <!-- Checklist options -->
          <div v-else class="flex flex-col gap-2.5">
            <div class="mb-0.5 flex flex-wrap items-center justify-between gap-2 rounded-lg bg-gray-100/80 px-3 py-2 text-xs text-gray-600 dark:bg-gray-700/40 dark:text-gray-300">
              <span>Выбрано пунктов: <strong>{{ getChecklistSelectedCount(criterion) }}</strong></span>
              <span v-if="saving === criterion.id">Сохраняем...</span>
              <span v-else-if="hasChecklistExclusiveSelected(criterion)">Выбран взаимоисключающий пункт</span>
              <span v-else>Можно выбрать несколько пунктов</span>
            </div>
            <button
              v-for="option in getChecklistOptions(criterion)"
              :key="option.id"
              type="button"
              class="w-full touch-manipulation cursor-pointer rounded-xl border px-3 py-3.5 text-left transition sm:px-4"
              :class="[
                isChecklistOptionSelected(criterion, option)
                  ? 'border-primary bg-primary-light/40 shadow-[0_1px_0_rgba(0,0,0,0.04)] dark:border-primary dark:bg-primary/20'
                  : 'border-gray-200 bg-white hover:border-primary/60 hover:bg-primary-light/40 dark:border-gray-700 dark:bg-gray-900/30 dark:hover:bg-primary/10',
                saving === criterion.id ? 'cursor-wait opacity-60' : '',
              ]"
              :disabled="saving === criterion.id"
              @click="toggleChecklistOption(criterion, option)"
            >
              <span class="flex items-center justify-between gap-3">
                <span class="flex min-w-0 items-center gap-3">
                  <span
                    class="flex h-5 w-5 shrink-0 items-center justify-center rounded border"
                    :class="isChecklistOptionSelected(criterion, option)
                      ? 'border-primary bg-primary text-white'
                      : 'border-gray-300 bg-white dark:border-gray-500 dark:bg-gray-800'"
                  >
                    <svg
                      v-if="isChecklistOptionSelected(criterion, option)"
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      class="h-3.5 w-3.5"
                    >
                      <path fill-rule="evenodd" d="M16.704 5.29a1 1 0 010 1.42l-7.2 7.2a1 1 0 01-1.414 0l-3-3a1 1 0 011.414-1.42L9 11.586l6.496-6.296a1 1 0 011.208 0z" clip-rule="evenodd" />
                    </svg>
                  </span>
                  <span class="min-w-0">
                    <span class="block text-sm font-medium leading-snug text-gray-800 dark:text-gray-100">
                      {{ option.title || `Пункт #${option.id}` }}
                    </span>
                  </span>
                </span>
                <span class="shrink-0 rounded-full bg-score-light px-2.5 py-1 text-xs font-semibold text-score">
                  +{{ formatChecklistOptionPoint(option.point) }}
                </span>
              </span>
            </button>
            <p v-if="!getChecklistOptions(criterion).length" class="text-xs text-gray-500 dark:text-gray-400">
              Для этого критерия не настроены пункты чеклиста.
            </p>
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
        class="sticky bottom-0 z-30 -mx-4 mt-4 overflow-hidden border-t px-5 py-3 text-white shadow-[0_-6px_20px_rgba(0,0,0,0.22)] transition-[border-radius,background-color,border-color] duration-200 sm:-mx-6"
        :class="[
          totalBarStuck ? 'rounded-t-xl' : 'rounded-xl',
          allCriteriaScored
            ? 'border-emerald-300/50 bg-emerald-600'
            : 'border-amber-300/50 bg-amber-600'
        ]"
      >
        <div class="relative flex flex-wrap items-center gap-2 text-base">
          <span class="font-medium">Итого:</span>
          <strong class="text-lg">{{ totalScore }}</strong>
          <span class="rounded-full border border-white/40 bg-white/15 px-2.5 py-0.5 text-xs font-medium text-white">
            {{ scoredCriteriaCount }}/{{ criteria.length }} критериев
          </span>
          <div class="ml-auto flex items-center gap-2">
            <transition name="fade">
              <span v-if="saved" class="text-sm font-medium text-green-100">Сохранено ✓</span>
            </transition>
            <router-link
              :to="{ name: 'works', params: { sheetId: props.sheetId } }"
              class="inline-flex items-center rounded-lg border border-white/80 bg-white px-3 py-1.5 text-sm font-semibold text-gray-900 no-underline shadow-sm ring-1 ring-black/5 transition hover:bg-gray-100"
              :class="hasPendingWrites ? 'pointer-events-none opacity-70' : ''"
            >
              К выбору работ
            </router-link>
          </div>
        </div>
        <div v-if="hasCategories" class="relative mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
          <span v-for="group in groupedCriteria" :key="group.category?.id ?? 'uncategorized'" v-show="group.category" class="text-xs text-white/75">
            {{ group.category?.title }}: <strong class="text-white">{{ categoryScore(group.category?.id) }}</strong>
          </span>
        </div>
      </div>
    </template>

    <!-- Scroll to top button -->
    <transition name="fade">
      <button
        v-show="showScrollTop"
        class="fixed bottom-20 right-5 z-50 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border-none bg-primary text-white shadow-lg transition hover:bg-primary-hover"
        @click="scrollToTop"
        title="Наверх"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M14.707 12.707a1 1 0 01-1.414 0L10 9.414l-3.293 3.293a1 1 0 01-1.414-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 010 1.414z" clip-rule="evenodd" />
        </svg>
      </button>
    </transition>
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
