<!--
  Сводный рейтинг работ по нескольким оценочным листам (Viewer/Admin).
  Построение выполняется на фронтенде "на лету":
    1) выбор листов;
    2) опционально выбор отдельных работ;
    3) формирование общей таблицы с местами.
-->
<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import api from '../api'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const sheets = ref([])
const loadingSheets = ref(true)
const loadingWorks = ref(false)
const loadingNormalization = ref(false)
const generating = ref(false)
const generated = ref(false)
const error = ref('')

const selectedSheetIds = ref([])
const selectIndividualWorks = ref(false)
const selectedWorkIds = ref([])
const useNormalizedScore = ref(false)
const includeCriterionScores = ref(false)
const includeCategoryScores = ref(false)
const exporting = ref(false)
const rankingKey = ref('total') // 'total' | `category:${categoryId}` | `criterion:${criterionId}`

const worksBySheet = reactive({})      // { [sheetId]: work[] }
const loadedWorksBySheet = reactive({}) // { [sheetId]: true }
const loadingSheetWorks = reactive({}) // { [sheetId]: boolean }
const scorecardMaxScore = reactive({}) // { [scorecardId]: number }
const criteriaByScorecard = reactive({}) // { [scorecardId]: criteria[] }
const categoriesByScorecard = reactive({}) // { [scorecardId]: categories[] }
const categoryScoresByWork = ref({}) // { [workId]: { [categoryId]: avgScore } }
const criterionScoresByWork = ref({}) // { [workId]: { [criterionId]: avgScore } }

const sheetMap = computed(() => {
  const map = {}
  for (const s of sheets.value) map[String(s.id)] = s
  return map
})

const selectedSheets = computed(() => (
  selectedSheetIds.value
    .map((id) => sheetMap.value[String(id)])
    .filter(Boolean)
))

const selectedWorksSet = computed(() => new Set(selectedWorkIds.value.map((id) => Number(id))))

const selectedSheetWorks = computed(() => (
  selectedSheets.value.map((sheet) => ({
    sheet,
    works: worksBySheet[sheet.id] || [],
  }))
))

const categoryColumns = computed(() => {
  if (!includeCategoryScores.value) return []

  const orderedScorecardIds = []
  const seenScorecards = new Set()
  for (const sheet of selectedSheets.value) {
    const scorecardId = Number(sheet?.scorecard_id)
    if (!scorecardId || seenScorecards.has(scorecardId)) continue
    seenScorecards.add(scorecardId)
    orderedScorecardIds.push(scorecardId)
  }

  const columns = []
  const seenCategories = new Set()
  for (const scorecardId of orderedScorecardIds) {
    const categories = categoriesByScorecard[scorecardId] || []
    const sorted = [...categories].sort((a, b) => {
      const orderA = a?.order != null ? Number(a.order) : Number.POSITIVE_INFINITY
      const orderB = b?.order != null ? Number(b.order) : Number.POSITIVE_INFINITY
      if (orderA !== orderB) return orderA - orderB
      return Number(a.id) - Number(b.id)
    })
    for (const category of sorted) {
      const categoryId = Number(category.id)
      if (!categoryId || seenCategories.has(categoryId)) continue
      seenCategories.add(categoryId)
      columns.push({
        id: categoryId,
        title: category.title || `Группа #${categoryId}`,
        key: `category:${categoryId}`,
      })
    }
  }

  const titleCounts = {}
  for (const column of columns) {
    titleCounts[column.title] = (titleCounts[column.title] || 0) + 1
  }

  return columns.map((column) => ({
    ...column,
    displayTitle: titleCounts[column.title] > 1 ? `${column.title} (#${column.id})` : column.title,
  }))
})

const criterionColumns = computed(() => {
  if (!includeCriterionScores.value) return []

  const orderedScorecardIds = []
  const seenScorecards = new Set()
  for (const sheet of selectedSheets.value) {
    const scorecardId = Number(sheet?.scorecard_id)
    if (!scorecardId || seenScorecards.has(scorecardId)) continue
    seenScorecards.add(scorecardId)
    orderedScorecardIds.push(scorecardId)
  }

  const columns = []
  const seenCriteria = new Set()
  for (const scorecardId of orderedScorecardIds) {
    const criteria = criteriaByScorecard[scorecardId] || []
    const sorted = [...criteria].sort((a, b) => {
      const orderA = a?.order != null ? Number(a.order) : Number.POSITIVE_INFINITY
      const orderB = b?.order != null ? Number(b.order) : Number.POSITIVE_INFINITY
      if (orderA !== orderB) return orderA - orderB
      return Number(a.id) - Number(b.id)
    })
    for (const criterion of sorted) {
      const criterionId = Number(criterion.id)
      if (!criterionId || seenCriteria.has(criterionId)) continue
      seenCriteria.add(criterionId)
      columns.push({
        id: criterionId,
        title: criterion.title || `Критерий #${criterionId}`,
        key: `criterion:${criterionId}`,
      })
    }
  }

  const titleCounts = {}
  for (const column of columns) {
    titleCounts[column.title] = (titleCounts[column.title] || 0) + 1
  }

  return columns.map((column) => ({
    ...column,
    displayTitle: titleCounts[column.title] > 1 ? `${column.title} (#${column.id})` : column.title,
  }))
})

const workRows = computed(() => {
  const rows = []
  for (const sheet of selectedSheets.value) {
    const works = worksBySheet[sheet.id] || []
    for (const work of works) {
      if (selectIndividualWorks.value && !selectedWorksSet.value.has(Number(work.id))) continue
      rows.push({
        id: Number(work.id),
        sheetId: Number(sheet.id),
        sheet,
        work,
      })
    }
  }
  return rows
})

const rankedRows = computed(() => {
  const categoryId = rankingKey.value.startsWith('category:')
    ? Number(rankingKey.value.split(':')[1])
    : null
  const criterionId = rankingKey.value.startsWith('criterion:')
    ? Number(rankingKey.value.split(':')[1])
    : null

  const rows = workRows.value.map((row) => {
    const rawScore = row.work.score != null ? Number(row.work.score) : null
    const maxScore = getSheetMaxScore(row.sheet)
    const normalizedScore = rawScore != null
      ? (maxScore > 0 ? (rawScore / maxScore) * 100 : rawScore)
      : null
    const categoryScores = categoryScoresByWork.value[row.id] || {}
    const criterionScores = criterionScoresByWork.value[row.id] || {}
    const categoryMetric = categoryId != null ? (categoryScores[categoryId] ?? null) : null
    const criterionMetric = criterionId != null ? (criterionScores[criterionId] ?? null) : null
    const metric = criterionId != null
      ? criterionMetric
      : (categoryId != null ? categoryMetric : (useNormalizedScore.value ? normalizedScore : rawScore))

    return {
      ...row,
      rawScore,
      normalizedScore,
      categoryScores,
      criterionScores,
      metric,
      rank: null,
    }
  })

  const scoredRows = rows
    .filter((row) => row.metric != null && !Number.isNaN(Number(row.metric)))
    .sort((a, b) => {
      const diff = b.metric - a.metric
      if (diff !== 0) return diff
      return getWorkTitle(a.work).localeCompare(getWorkTitle(b.work), 'ru')
    })

  let previousMetric = null
  let currentRank = 0
  for (let i = 0; i < scoredRows.length; i++) {
    const row = scoredRows[i]
    if (previousMetric == null || Math.abs(row.metric - previousMetric) > 1e-9) {
      currentRank += 1
      row.rank = currentRank
      previousMetric = row.metric
    } else {
      row.rank = currentRank
    }
  }

  const unscoredRows = rows
    .filter((row) => row.metric == null || Number.isNaN(Number(row.metric)))
    .sort((a, b) => getWorkTitle(a.work).localeCompare(getWorkTitle(b.work), 'ru'))

  return [...scoredRows, ...unscoredRows]
})

const hasSelectedSheets = computed(() => selectedSheetIds.value.length > 0)
const canExport = computed(() => generated.value && rankedRows.value.length > 0 && !exporting.value)
const canGenerate = computed(() => {
  if (!hasSelectedSheets.value) return false
  if (!selectIndividualWorks.value) return true
  return selectedWorkIds.value.length > 0
})

watch(selectedSheetIds, async (ids) => {
  generated.value = false
  await ensureWorksLoaded(ids)
  pruneSelectedWorks()
}, { immediate: false })

watch(selectIndividualWorks, (enabled) => {
  generated.value = false
  if (!enabled) {
    selectedWorkIds.value = []
    return
  }
  selectAllLoadedWorks()
})

watch(useNormalizedScore, () => {
  generated.value = false
})

watch(includeCriterionScores, (enabled) => {
  generated.value = false
  if (!enabled) {
    criterionScoresByWork.value = {}
    if (rankingKey.value.startsWith('criterion:')) rankingKey.value = 'total'
  }
})

watch(includeCategoryScores, (enabled) => {
  generated.value = false
  if (!enabled) {
    categoryScoresByWork.value = {}
    if (rankingKey.value.startsWith('category:')) rankingKey.value = 'total'
  }
})

function setScoreDetailsMode(mode) {
  if (mode === 'category') {
    includeCriterionScores.value = false
    includeCategoryScores.value = true
    return
  }
  if (mode === 'criterion') {
    includeCategoryScores.value = false
    includeCriterionScores.value = true
    return
  }
  includeCategoryScores.value = false
  includeCriterionScores.value = false
}

onMounted(() => {
  loadSheets()
})

async function loadSheets() {
  loadingSheets.value = true
  error.value = ''
  try {
    const { data } = await api.get('/contest_evaluation_sheets:list', {
      params: {
        appends: 'observers,contest,stage',
        pageSize: 500,
      },
    })
    const personId = auth.personId != null ? Number(auth.personId) : null
    const userId = auth.user?.id != null ? Number(auth.user.id) : null
    const canObserveSheet = (sheet) => {
      if (auth.isAdmin) return true
      const observers = Array.isArray(sheet?.observers) ? sheet.observers : []
      return observers.some((observer) => {
        const observerId = observer?.id != null ? Number(observer.id) : null
        const observerUserId = observer?.user_id != null ? Number(observer.user_id) : null
        if (personId != null && observerId === personId) return true
        if (userId != null && (observerId === userId || observerUserId === userId)) return true
        return false
      })
    }

    sheets.value = (data.data || [])
      .filter((sheet) => {
        const status = sheet.status || 'inactive'
        if (status !== 'active' && status !== 'inactive') return false
        return canObserveSheet(sheet)
      })
      .sort((a, b) => {
        const contestA = a.contest?.title || ''
        const contestB = b.contest?.title || ''
        if (contestA !== contestB) return contestA.localeCompare(contestB, 'ru')
        return (a.title || '').localeCompare(b.title || '', 'ru')
      })
  } catch {
    error.value = 'Не удалось загрузить оценочные листы'
  } finally {
    loadingSheets.value = false
  }
}

async function ensureWorksLoaded(sheetIds) {
  const ids = sheetIds.map((id) => Number(id))
  const toLoad = ids.filter((sheetId) => !loadedWorksBySheet[sheetId] && !loadingSheetWorks[sheetId])
  if (!toLoad.length) return

  loadingWorks.value = true
  error.value = ''
  try {
    await Promise.all(toLoad.map(async (sheetId) => {
      loadingSheetWorks[sheetId] = true
      try {
        const { data } = await api.get('/contest_evaluation_sheet_works:list', {
          params: {
            filter: JSON.stringify({ sheet_id: sheetId }),
            appends: 'participation,participation.participants,participation.supervisors',
            sort: 'order,id',
            pageSize: 1000,
          },
        })
        worksBySheet[sheetId] = data.data || []
        loadedWorksBySheet[sheetId] = true
      } finally {
        loadingSheetWorks[sheetId] = false
      }
    }))
  } catch {
    error.value = 'Не удалось загрузить работы выбранных листов'
  } finally {
    loadingWorks.value = false
  }
}

function pruneSelectedWorks() {
  if (!selectIndividualWorks.value) return

  const availableIds = new Set()
  for (const sheetId of selectedSheetIds.value.map((id) => Number(id))) {
    const works = worksBySheet[sheetId] || []
    for (const work of works) availableIds.add(Number(work.id))
  }
  selectedWorkIds.value = selectedWorkIds.value.filter((id) => availableIds.has(Number(id)))
}

function selectAllSheets() {
  selectedSheetIds.value = sheets.value.map((sheet) => sheet.id)
}

function clearSelectedSheets() {
  selectedSheetIds.value = []
  selectedWorkIds.value = []
  generated.value = false
}

function selectAllLoadedWorks() {
  const ids = []
  for (const sheetId of selectedSheetIds.value.map((id) => Number(id))) {
    const works = worksBySheet[sheetId] || []
    for (const work of works) ids.push(Number(work.id))
  }
  selectedWorkIds.value = ids
}

function clearSelectedWorks() {
  selectedWorkIds.value = []
}

function isAllWorksSelectedInSheet(sheetId) {
  const works = worksBySheet[Number(sheetId)] || []
  if (!works.length) return false
  return works.every((work) => selectedWorksSet.value.has(Number(work.id)))
}

function toggleAllWorksInSheet(sheetId) {
  const works = worksBySheet[Number(sheetId)] || []
  if (!works.length) return

  const selected = new Set(selectedWorksSet.value)
  const shouldSelectAll = !isAllWorksSelectedInSheet(sheetId)

  for (const work of works) {
    const workId = Number(work.id)
    if (shouldSelectAll) selected.add(workId)
    else selected.delete(workId)
  }
  selectedWorkIds.value = [...selected]
}

function setTotalRanking() {
  rankingKey.value = 'total'
}

function setCategoryRanking(categoryId) {
  rankingKey.value = `category:${Number(categoryId)}`
}

function setCriterionRanking(criterionId) {
  rankingKey.value = `criterion:${Number(criterionId)}`
}

function rankingMarker(columnKey) {
  return rankingKey.value === columnKey ? '↓' : ''
}

async function ensureCriteriaDefinitions() {
  const scorecardIds = [
    ...new Set(
      selectedSheets.value
        .map((sheet) => Number(sheet?.scorecard_id))
        .filter(Boolean),
    ),
  ]
  const toLoad = scorecardIds.filter((id) => !(id in criteriaByScorecard))
  if (!toLoad.length) return

  await Promise.all(toLoad.map(async (scorecardId) => {
    const { data } = await api.get('/contest_scorecard_criteria:list', {
      params: {
        filter: JSON.stringify({ scorecard_id: scorecardId }),
        sort: 'order,id',
        pageSize: 1000,
      },
    })
    criteriaByScorecard[scorecardId] = data.data || []
  }))
}

async function ensureCategoryDefinitions() {
  const scorecardIds = [
    ...new Set(
      selectedSheets.value
        .map((sheet) => Number(sheet?.scorecard_id))
        .filter(Boolean),
    ),
  ]
  const toLoad = scorecardIds.filter((id) => !(id in categoriesByScorecard))
  if (!toLoad.length) return

  await Promise.all(toLoad.map(async (scorecardId) => {
    const { data } = await api.get('/contest_criterion_categories:list', {
      params: {
        filter: JSON.stringify({ scorecard_id: scorecardId }),
        sort: 'order,id',
        pageSize: 1000,
      },
    })
    categoriesByScorecard[scorecardId] = data.data || []
  }))
}

async function ensureDetailedScoresData() {
  const rows = workRows.value
  const categoryIds = includeCategoryScores.value
    ? categoryColumns.value.map((column) => Number(column.id)).filter(Boolean)
    : []
  const criterionIds = includeCriterionScores.value
    ? criterionColumns.value.map((column) => Number(column.id)).filter(Boolean)
    : []
  if (!rows.length || (!categoryIds.length && !criterionIds.length)) {
    categoryScoresByWork.value = {}
    criterionScoresByWork.value = {}
    return
  }

  const workIds = [...new Set(rows.map((row) => Number(row.id)).filter(Boolean))]
  const categoryIdSet = new Set(categoryIds)
  const criterionIdSet = new Set(criterionIds)

  const categoryIdByCriterionId = {}
  for (const criteria of Object.values(criteriaByScorecard)) {
    for (const criterion of criteria || []) {
      const critId = Number(criterion?.id)
      if (!critId) continue
      const catId = criterion?.category_id != null ? Number(criterion.category_id) : null
      categoryIdByCriterionId[critId] = catId
    }
  }

  const { data: evalData } = await api.get('/contest_evaluations:list', {
    params: {
      filter: JSON.stringify({ sheet_work_id: { $in: workIds } }),
      pageSize: 10000,
    },
  })
  const evaluations = evalData.data || []
  const evalIds = evaluations.map((ev) => Number(ev.id)).filter(Boolean)

  const judgeCountByWork = {}
  const workIdByEvaluationId = {}
  for (const evaluation of evaluations) {
    const workId = Number(evaluation.sheet_work_id)
    if (!workId) continue
    judgeCountByWork[workId] = (judgeCountByWork[workId] || 0) + 1
    workIdByEvaluationId[Number(evaluation.id)] = workId
  }

  let items = []
  if (evalIds.length) {
    const { data: itemData } = await api.get('/contest_evaluation_items:list', {
      params: {
        filter: JSON.stringify({ evaluation_id: { $in: evalIds } }),
        pageSize: 50000,
      },
    })
    items = itemData.data || []
  }

  const categorySumsByWork = {}
  const sumsByWork = {}
  for (const item of items) {
    const criterionId = Number(item.criterion_id)
    const score = item.score != null ? Number(item.score) : NaN
    if (Number.isNaN(score)) continue
    const workId = workIdByEvaluationId[Number(item.evaluation_id)]
    if (!workId) continue

    if (criterionIdSet.has(criterionId)) {
      if (!sumsByWork[workId]) sumsByWork[workId] = {}
      sumsByWork[workId][criterionId] = (sumsByWork[workId][criterionId] || 0) + score
    }

    const categoryId = categoryIdByCriterionId[criterionId]
    if (categoryIdSet.has(categoryId)) {
      if (!categorySumsByWork[workId]) categorySumsByWork[workId] = {}
      categorySumsByWork[workId][categoryId] = (categorySumsByWork[workId][categoryId] || 0) + score
    }
  }

  const categoryResult = {}
  const criterionResult = {}
  for (const workId of workIds) {
    const judgeCount = judgeCountByWork[workId] || 0
    const categoryScores = {}
    const criterionScores = {}

    for (const categoryId of categoryIds) {
      if (!judgeCount) {
        categoryScores[categoryId] = null
      } else {
        const sum = categorySumsByWork[workId]?.[categoryId] || 0
        categoryScores[categoryId] = +(sum / judgeCount).toFixed(2)
      }
    }

    for (const criterionId of criterionIds) {
      if (!judgeCount) {
        criterionScores[criterionId] = null
      } else {
        const sum = sumsByWork[workId]?.[criterionId] || 0
        criterionScores[criterionId] = +(sum / judgeCount).toFixed(2)
      }
    }

    categoryResult[workId] = categoryScores
    criterionResult[workId] = criterionScores
  }

  categoryScoresByWork.value = categoryResult
  criterionScoresByWork.value = criterionResult
}

async function generateRanking() {
  if (!canGenerate.value) return

  generating.value = true
  const startedAt = Date.now()
  error.value = ''

  // Даём Vue отрисовать toast и спиннер перед выполнением расчётов
  await nextTick()
  await sleep(50)

  try {
    await ensureWorksLoaded(selectedSheetIds.value)
    if (useNormalizedScore.value) {
      await ensureNormalizationData()
    }
    if (includeCriterionScores.value || includeCategoryScores.value) {
      await ensureCriteriaDefinitions()
      await ensureCategoryDefinitions()
      await ensureDetailedScoresData()
    } else {
      categoryScoresByWork.value = {}
      criterionScoresByWork.value = {}
    }
    if (
      rankingKey.value.startsWith('category:')
      && !categoryColumns.value.some((column) => column.key === rankingKey.value)
    ) {
      rankingKey.value = 'total'
    }
    if (
      rankingKey.value.startsWith('criterion:')
      && !criterionColumns.value.some((column) => column.key === rankingKey.value)
    ) {
      rankingKey.value = 'total'
    }
    generated.value = true
  } catch {
    error.value = 'Не удалось сформировать сводный рейтинг'
  } finally {
    // Минимальная длительность показа индикатора
    const elapsed = Date.now() - startedAt
    if (elapsed < 450) {
      await sleep(450 - elapsed)
    }
    generating.value = false
  }
}

async function ensureNormalizationData() {
  loadingNormalization.value = true
  try {
    const selectedScorecardIds = [
      ...new Set(
        selectedSheets.value
          .map((sheet) => Number(sheet.scorecard_id))
          .filter(Boolean),
      ),
    ]
    const scorecardsToLoad = selectedScorecardIds.filter((id) => !(id in scorecardMaxScore))
    if (!scorecardsToLoad.length) return

    await Promise.all(scorecardsToLoad.map(async (scorecardId) => {
      const { data: criteriaData } = await api.get('/contest_scorecard_criteria:list', {
        params: {
          filter: JSON.stringify({ scorecard_id: scorecardId }),
          pageSize: 1000,
        },
      })
      const criteria = criteriaData.data || []
      const scaleIds = [...new Set(criteria.map((criterion) => criterion.scale_id).filter(Boolean))]

      if (!scaleIds.length) {
        scorecardMaxScore[scorecardId] = 0
        return
      }

      const { data: levelsData } = await api.get('/contest_criterion_scale_levels:list', {
        params: {
          filter: JSON.stringify({ scale_id: { $in: scaleIds } }),
          pageSize: 5000,
        },
      })

      const levels = levelsData.data || []
      const maxByScale = {}

      for (const level of levels) {
        const scaleId = level.scale_id
        const point = Number(level.point ?? level.score ?? 0)
        if (maxByScale[scaleId] == null || point > maxByScale[scaleId]) {
          maxByScale[scaleId] = point
        }
      }

      let maxScore = 0
      for (const criterion of criteria) {
        maxScore += Number(maxByScale[criterion.scale_id] ?? 0)
      }

      scorecardMaxScore[scorecardId] = maxScore
    }))
  } finally {
    loadingNormalization.value = false
  }
}

function getSheetMaxScore(sheet) {
  const scorecardId = Number(sheet?.scorecard_id)
  if (!scorecardId) return 0
  return Number(scorecardMaxScore[scorecardId] ?? 0)
}

function getWorkParticipation(work) {
  return work?.participation || work?.stage_participation?.participation || null
}

function getWorkTitle(work) {
  return getWorkParticipation(work)?.title
    || work?.stage_participation?.title
    || `Работа #${work.id}`
}

function getParticipants(work) {
  return getWorkParticipation(work)?.participants || []
}

function getParticipation(work) {
  return getWorkParticipation(work)
}

function isExternalWork(work) {
  return !!getParticipation(work)?.is_external
}

function getSupervisors(work) {
  return getWorkParticipation(work)?.supervisors || []
}

function formatScore(value, digits = 2) {
  if (value == null || Number.isNaN(Number(value))) return '—'
  return Number(value).toLocaleString('ru-RU', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function getSheetSubtitle(sheet) {
  const contest = sheet.contest?.title
  const stage = sheet.stage?.title
  if (contest && stage) return `${contest} · ${stage}`
  return contest || stage || ''
}

function getParticipantNames(work) {
  return getParticipants(work)
    .map((p) => p.full_name || p.short_name)
    .filter(Boolean)
    .join(', ')
}

function getSupervisorNames(work) {
  return getSupervisors(work)
    .map((s) => s.full_name || s.short_name)
    .filter(Boolean)
    .join(', ')
}

function getExportColumns() {
  const cols = [
    { key: 'index', title: '№', min: 6, max: 10 },
    { key: 'workTitle', title: 'Работа', min: 28, max: 60 },
    { key: 'participants', title: 'Участники', min: 22, max: 42 },
    { key: 'supervisors', title: 'Супервайзеры', min: 30, max: 70 },
    { key: 'rawScore', title: 'Балл', min: 10, max: 16 },
    { key: 'rank', title: 'Место', min: 8, max: 12 },
  ]
  if (includeCategoryScores.value && categoryColumns.value.length) {
    for (const column of categoryColumns.value) {
      cols.push({
        key: column.key,
        title: column.displayTitle,
        min: 12,
        max: 24,
      })
    }
  }
  if (includeCriterionScores.value && criterionColumns.value.length) {
    for (const column of criterionColumns.value) {
      cols.push({
        key: column.key,
        title: column.displayTitle,
        min: 12,
        max: 24,
      })
    }
  }
  if (useNormalizedScore.value) {
    cols.push({ key: 'normalizedScore', title: 'Нормализованный балл (0-100)', min: 20, max: 30 })
  }
  return cols
}

function getExportRows() {
  return rankedRows.value.map((row, index) => {
    const exportRow = {
      index: index + 1,
      rank: row.rank ?? '',
      workTitle: getWorkTitle(row.work),
      participants: getParticipantNames(row.work) || '—',
      supervisors: getSupervisorNames(row.work) || '—',
      rawScore: row.rawScore != null ? Number(row.rawScore.toFixed(2)) : '',
      normalizedScore: useNormalizedScore.value && row.normalizedScore != null
        ? Number(row.normalizedScore.toFixed(2))
        : '',
    }
    if (includeCriterionScores.value && criterionColumns.value.length) {
      for (const column of criterionColumns.value) {
        const value = row.criterionScores?.[column.id]
        exportRow[column.key] = value != null && !Number.isNaN(Number(value))
          ? Number(Number(value).toFixed(2))
          : ''
      }
    }
    if (includeCategoryScores.value && categoryColumns.value.length) {
      for (const column of categoryColumns.value) {
        const value = row.categoryScores?.[column.id]
        exportRow[column.key] = value != null && !Number.isNaN(Number(value))
          ? Number(Number(value).toFixed(2))
          : ''
      }
    }
    return exportRow
  })
}

function longestCellLength(value) {
  if (value == null) return 0
  const str = String(value)
  return str
    .split('\n')
    .reduce((max, part) => Math.max(max, part.length), 0)
}

function buildColumnWidths(columns, rows) {
  return columns.map((column) => {
    let width = longestCellLength(column.title)
    for (const row of rows) {
      const len = longestCellLength(row[column.key])
      if (len > width) width = len
    }
    const padded = width + 2
    return Math.max(column.min, Math.min(column.max, padded))
  })
}

function getExportTitle() {
  return selectedSheets.value[0]?.title || 'Оценочный лист'
}

function getExportFileName() {
  const now = new Date()
  const yyyy = now.getFullYear()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  return `svodnyi-reiting-${yyyy}-${mm}-${dd}_${hh}-${min}.xlsx`
}

function triggerFileDownload(blob, fileName) {
  const link = document.createElement('a')
  const url = URL.createObjectURL(blob)
  link.href = url
  link.download = fileName
  document.body.appendChild(link)
  link.click()
  link.remove()
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

async function exportToExcel() {
  if (!canExport.value) return

  exporting.value = true
  const startedAt = Date.now()

  // Даём Vue отрисовать toast-индикатор перед синхронной генерацией файла
  await nextTick()
  await sleep(50)

  try {
    const exceljsModule = await import('exceljs')
    const ExcelJS = exceljsModule.default || exceljsModule
    const columns = getExportColumns()
    const rows = getExportRows()
    const colWidths = buildColumnWidths(columns, rows)
    const title = getExportTitle()
    const headerRow = 3
    const dataStartRow = headerRow + 1
    const lastCol = columns.length - 1
    const workbook = new ExcelJS.Workbook()
    const worksheet = workbook.addWorksheet('Сводный рейтинг')
    const indexColIdx = columns.findIndex((col) => col.key === 'index')
    const rankColIdx = columns.findIndex((col) => col.key === 'rank')

    worksheet.columns = columns.map((column, idx) => ({
      key: column.key,
      width: colWidths[idx],
    }))

    worksheet.mergeCells(1, 1, 1, lastCol + 1)
    worksheet.getCell(1, 1).value = title
    worksheet.getCell(1, 1).font = { bold: true, size: 14 }
    worksheet.getCell(1, 1).alignment = { vertical: 'top' }

    for (let col = 0; col < columns.length; col++) {
      const cell = worksheet.getCell(headerRow, col + 1)
      cell.value = columns[col].title
      cell.font = { bold: true, color: { argb: 'FF111827' } }
      cell.fill = {
        type: 'pattern',
        pattern: 'solid',
        fgColor: { argb: 'FFF3F4F6' },
      }
      cell.border = {
        top: { style: 'thin', color: { argb: 'FF000000' } },
        left: { style: 'thin', color: { argb: 'FF000000' } },
        bottom: { style: 'thin', color: { argb: 'FF000000' } },
        right: { style: 'thin', color: { argb: 'FF000000' } },
      }
      cell.alignment = { vertical: 'middle', horizontal: 'center', wrapText: true }
    }

    const rawScoreIdx = columns.findIndex((col) => col.key === 'rawScore')
    const normalizedScoreIdx = columns.findIndex((col) => col.key === 'normalizedScore')
    const categoryColumnIndexes = columns
      .map((column, idx) => (String(column.key).startsWith('category:') ? idx : -1))
      .filter((idx) => idx >= 0)
    const criterionColumnIndexes = columns
      .map((column, idx) => (String(column.key).startsWith('criterion:') ? idx : -1))
      .filter((idx) => idx >= 0)
    const centeredColumnIndexes = [indexColIdx, rankColIdx, rawScoreIdx, normalizedScoreIdx, ...categoryColumnIndexes, ...criterionColumnIndexes]
      .filter((idx) => idx >= 0)
    const wrapColumnIndexes = ['workTitle', 'participants', 'supervisors']
      .map((key) => columns.findIndex((col) => col.key === key))
      .filter((idx) => idx >= 0)

    for (let i = 0; i < rows.length; i++) {
      const rowNumber = dataStartRow + i
      const rowData = rows[i]

      for (let col = 0; col < columns.length; col++) {
        const key = columns[col].key
        let value = rowData[key]

        if (
          key === 'rawScore'
          || key === 'normalizedScore'
          || String(key).startsWith('category:')
          || String(key).startsWith('criterion:')
        ) {
          value = value === '' || value == null ? null : Number(value)
          if (Number.isNaN(value)) value = null
        }

        const cell = worksheet.getCell(rowNumber, col + 1)
        cell.value = value === '' ? null : value
        cell.border = {
          top: { style: 'thin', color: { argb: 'FF000000' } },
          left: { style: 'thin', color: { argb: 'FF000000' } },
          bottom: { style: 'thin', color: { argb: 'FF000000' } },
          right: { style: 'thin', color: { argb: 'FF000000' } },
        }
        cell.alignment = {
          vertical: 'top',
          horizontal: centeredColumnIndexes.includes(col) ? 'center' : 'left',
        }
      }

      for (const colIdx of wrapColumnIndexes) {
        const cell = worksheet.getCell(rowNumber, colIdx + 1)
        cell.alignment = {
          ...(cell.alignment || {}),
          wrapText: true,
          vertical: 'top',
        }
      }

      if (rawScoreIdx >= 0) {
        const cell = worksheet.getCell(rowNumber, rawScoreIdx + 1)
        if (typeof cell.value === 'number') cell.numFmt = '0.00'
      }
      if (normalizedScoreIdx >= 0) {
        const cell = worksheet.getCell(rowNumber, normalizedScoreIdx + 1)
        if (typeof cell.value === 'number') cell.numFmt = '0.00'
      }
      for (const colIdx of categoryColumnIndexes) {
        const cell = worksheet.getCell(rowNumber, colIdx + 1)
        if (typeof cell.value === 'number') cell.numFmt = '0.00'
      }
      for (const colIdx of criterionColumnIndexes) {
        const cell = worksheet.getCell(rowNumber, colIdx + 1)
        if (typeof cell.value === 'number') cell.numFmt = '0.00'
      }
    }

    const buffer = await workbook.xlsx.writeBuffer()
    const blob = new Blob(
      [buffer],
      { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' },
    )
    triggerFileDownload(blob, getExportFileName())
  } finally {
    // Минимальная длительность показа индикатора, чтобы пользователь успел заметить его
    const elapsed = Date.now() - startedAt
    if (elapsed < 450) {
      await sleep(450 - elapsed)
    }
    exporting.value = false
  }
}
</script>

<template>
  <div>
    <div class="mb-4">
      <router-link :to="{ name: 'results-sheets' }" class="text-sm text-primary no-underline hover:underline">
        &larr; К оценочным листам
      </router-link>
    </div>

    <div class="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="text-2xl font-bold text-gray-900 dark:text-gray-100">Сводный рейтинг</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Выберите листы и при необходимости отдельные работы, затем сформируйте общий ранг.
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <button
          @click="generateRanking"
          :disabled="!canGenerate || generating || loadingNormalization"
          class="inline-flex min-w-[220px] cursor-pointer items-center justify-center gap-2 rounded-lg border-none bg-primary px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-hover disabled:cursor-default disabled:opacity-50"
        >
          <svg
            v-if="generating"
            class="h-4 w-4 animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          <span>Сформировать рейтинг</span>
        </button>
        <button
          @click="exportToExcel"
          :disabled="!canExport || generating || exporting"
          class="inline-flex min-w-[180px] cursor-pointer items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-default disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          <svg
            v-if="exporting"
            class="h-4 w-4 animate-spin text-primary"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
          </svg>
          <span>Экспорт в Excel</span>
        </button>
      </div>
    </div>

    <div v-if="loadingSheets" class="flex items-center justify-center gap-3 py-10 text-gray-500">
      <svg class="h-5 w-5 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" /><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" /></svg>
      <span>Загрузка листов...</span>
    </div>

    <p v-else-if="error" class="py-8 text-center text-red-600">{{ error }}</p>

    <template v-else>
      <div class="mb-4 flex flex-wrap items-center gap-2">
        <button
          @click="selectAllSheets"
          class="cursor-pointer rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          Выбрать все листы
        </button>
        <button
          @click="clearSelectedSheets"
          class="cursor-pointer rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
        >
          Очистить выбор
        </button>
      </div>

      <div class="grid gap-3 sm:grid-cols-2">
        <label
          v-for="sheet in sheets"
          :key="sheet.id"
          class="flex cursor-pointer items-start gap-3 rounded-xl border border-gray-200 bg-white px-4 py-3 dark:border-gray-700 dark:bg-gray-800"
        >
          <input
            v-model="selectedSheetIds"
            :value="sheet.id"
            type="checkbox"
            class="mt-0.5 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
          >
          <div class="min-w-0">
            <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ sheet.title }}</div>
            <div v-if="getSheetSubtitle(sheet)" class="mt-0.5 text-xs text-gray-500 dark:text-gray-400">{{ getSheetSubtitle(sheet) }}</div>
            <div class="mt-1 text-xs" :class="(sheet.status || 'inactive') === 'active' ? 'text-green-600' : 'text-yellow-600'">
              {{ (sheet.status || 'inactive') === 'active' ? 'Активный' : 'Неактивный' }}
            </div>
          </div>
        </label>
      </div>

      <div class="mt-5 flex flex-col gap-2 rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
        <label class="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input v-model="selectIndividualWorks" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary">
          Выбирать отдельные работы
        </label>
        <label class="inline-flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
          <input v-model="useNormalizedScore" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary">
          Нормализовать баллы к 100 (для листов с разными шкалами)
        </label>
        <div class="mt-1 text-sm text-gray-700 dark:text-gray-300">
          <div class="mb-1 font-medium">Детализация баллов:</div>
          <div class="flex flex-wrap items-center gap-4">
            <label class="inline-flex items-center gap-2">
              <input
                type="radio"
                name="score-details-mode"
                class="h-4 w-4 border-gray-300 text-primary focus:ring-primary"
                :checked="!includeCategoryScores && !includeCriterionScores"
                @change="setScoreDetailsMode('none')"
              >
              Без детализации
            </label>
            <label class="inline-flex items-center gap-2">
              <input
                type="radio"
                name="score-details-mode"
                class="h-4 w-4 border-gray-300 text-primary focus:ring-primary"
                :checked="includeCategoryScores"
                @change="setScoreDetailsMode('category')"
              >
              По группам критериев
            </label>
            <label class="inline-flex items-center gap-2">
              <input
                type="radio"
                name="score-details-mode"
                class="h-4 w-4 border-gray-300 text-primary focus:ring-primary"
                :checked="includeCriterionScores"
                @change="setScoreDetailsMode('criterion')"
              >
              По отдельным критериям
            </label>
          </div>
        </div>
        <p v-if="useNormalizedScore" class="text-xs text-gray-500 dark:text-gray-400">
          Итоговый ранг считается по нормализованному баллу.
        </p>
        <p v-if="includeCriterionScores || includeCategoryScores" class="text-xs text-gray-500 dark:text-gray-400">
          После формирования можно кликнуть по заголовку нужного столбца для ранжирования по нему.
        </p>
      </div>

      <div v-if="loadingWorks" class="mt-3 text-sm text-gray-500 dark:text-gray-400">Загрузка работ выбранных листов...</div>

      <div v-if="selectIndividualWorks && hasSelectedSheets" class="mt-5">
        <div class="mb-3 flex flex-wrap items-center gap-2">
          <button
            @click="selectAllLoadedWorks"
            class="cursor-pointer rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Выбрать все работы
          </button>
          <button
            @click="clearSelectedWorks"
            class="cursor-pointer rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-sm text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          >
            Снять выбор работ
          </button>
          <span class="text-sm text-gray-500 dark:text-gray-400">Выбрано: {{ selectedWorkIds.length }}</span>
        </div>

        <div class="flex flex-col gap-4">
          <section
            v-for="group in selectedSheetWorks"
            :key="group.sheet.id"
            class="rounded-xl border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800"
          >
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
              <div>
                <h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">{{ group.sheet.title }}</h2>
                <p v-if="group.works.length" class="text-xs text-gray-500 dark:text-gray-400">Работ: {{ group.works.length }}</p>
              </div>
              <button
                @click="toggleAllWorksInSheet(group.sheet.id)"
                class="cursor-pointer rounded-lg border border-gray-200 bg-white px-3 py-1 text-xs text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              >
                {{ isAllWorksSelectedInSheet(group.sheet.id) ? 'Снять все' : 'Выбрать все' }}
              </button>
            </div>

            <p v-if="!group.works.length" class="text-sm text-gray-500 dark:text-gray-400">В этом листе нет работ.</p>

            <div v-else class="flex flex-col gap-2">
              <label
                v-for="work in group.works"
                :key="work.id"
                class="flex cursor-pointer items-start gap-3 rounded-lg border border-gray-100 px-3 py-2 dark:border-gray-700"
              >
                <input
                  v-model="selectedWorkIds"
                  :value="work.id"
                  type="checkbox"
                  class="mt-1 h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary"
                >
                <div class="min-w-0">
                  <div class="flex flex-wrap items-center gap-1.5 text-sm font-medium text-gray-800 dark:text-gray-200">
                    <span>{{ getWorkTitle(work) }}</span>
                    <span
                      v-if="isExternalWork(work)"
                      class="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                    >
                      Внешний участник
                    </span>
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">
                    Участники: {{ getParticipantNames(work) || '—' }}
                  </div>
                  <div class="text-xs text-score">Балл: {{ formatScore(work.score) }}</div>
                </div>
              </label>
            </div>
          </section>
        </div>
      </div>

      <div v-if="generated" class="mt-6">
        <h2 class="mb-3 text-xl font-semibold text-gray-900 dark:text-gray-100">Результат</h2>

        <p v-if="!rankedRows.length" class="py-6 text-center text-gray-500 dark:text-gray-400">
          Нет данных для построения ранга.
        </p>

        <div v-else class="overflow-x-auto rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <table class="min-w-full border-collapse">
            <thead class="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-900/30">
              <tr>
                <th class="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-gray-500">№</th>
                <th class="min-w-[36rem] w-[36rem] px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Работа</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Супервайзеры</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Лист</th>
                <th
                  class="cursor-pointer px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide select-none"
                  :class="rankingKey === 'total' ? 'text-primary' : 'text-gray-500'"
                  @click="setTotalRanking"
                >
                  Балл <span class="ml-1">{{ rankingMarker('total') }}</span>
                </th>
                <th class="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-gray-500">Место</th>
                <th
                  v-for="category in categoryColumns"
                  :key="category.id"
                  class="cursor-pointer px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide select-none"
                  :class="rankingKey === category.key ? 'text-primary' : 'text-gray-500'"
                  @click="setCategoryRanking(category.id)"
                >
                  {{ category.displayTitle }} <span class="ml-1">{{ rankingMarker(category.key) }}</span>
                </th>
                <th
                  v-for="criterion in criterionColumns"
                  :key="criterion.id"
                  class="cursor-pointer px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide select-none"
                  :class="rankingKey === criterion.key ? 'text-primary' : 'text-gray-500'"
                  @click="setCriterionRanking(criterion.id)"
                >
                  {{ criterion.displayTitle }} <span class="ml-1">{{ rankingMarker(criterion.key) }}</span>
                </th>
                <th
                  v-if="useNormalizedScore"
                  class="px-3 py-2 text-center text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Норм. балл
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, rowIndex) in rankedRows"
                :key="`${row.sheetId}-${row.id}`"
                class="border-b border-gray-100 last:border-b-0 dark:border-gray-700"
              >
                <td class="px-3 py-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
                  {{ rowIndex + 1 }}
                </td>
                <td class="min-w-[36rem] w-[36rem] px-3 py-2">
                  <div class="flex flex-wrap items-center gap-1.5 text-sm font-medium text-gray-900 dark:text-gray-100">
                    <span>{{ getWorkTitle(row.work) }}</span>
                    <span
                      v-if="isExternalWork(row.work)"
                      class="inline-block rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-700 dark:bg-blue-900/40 dark:text-blue-300"
                    >
                      Внешний участник
                    </span>
                  </div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">
                    {{ getParticipantNames(row.work) || '—' }}
                  </div>
                </td>
                <td class="px-3 py-2 text-sm text-gray-600 dark:text-gray-300">
                  {{ getSupervisors(row.work).map((s) => s.full_name || s.short_name).join(', ') || '—' }}
                </td>
                <td class="px-3 py-2 text-sm text-gray-600 dark:text-gray-300">
                  {{ row.sheet.title }}
                </td>
                <td class="px-3 py-2 text-center text-sm font-semibold text-score">
                  {{ formatScore(row.rawScore) }}
                </td>
                <td class="px-3 py-2 text-center text-sm font-semibold text-gray-700 dark:text-gray-200">
                  {{ row.rank ?? '—' }}
                </td>
                <td
                  v-for="category in categoryColumns"
                  :key="`category-${row.sheetId}-${row.id}-${category.id}`"
                  class="px-3 py-2 text-center text-sm font-semibold"
                  :class="rankingKey === category.key ? 'text-primary' : 'text-gray-600 dark:text-gray-300'"
                >
                  {{ formatScore(row.categoryScores?.[category.id]) }}
                </td>
                <td
                  v-for="criterion in criterionColumns"
                  :key="`criterion-${row.sheetId}-${row.id}-${criterion.id}`"
                  class="px-3 py-2 text-center text-sm font-semibold"
                  :class="rankingKey === criterion.key ? 'text-primary' : 'text-gray-600 dark:text-gray-300'"
                >
                  {{ formatScore(row.criterionScores?.[criterion.id]) }}
                </td>
                <td v-if="useNormalizedScore" class="px-3 py-2 text-center text-sm font-semibold text-primary">
                  {{ formatScore(row.normalizedScore) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <transition-group
      tag="div"
      class="pointer-events-none fixed bottom-4 right-4 z-30 flex max-w-xs flex-col gap-2 sm:max-w-sm"
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="translate-y-1 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-1 opacity-0"
    >
      <div
        v-if="generating"
        key="generating-toast"
        class="flex items-center gap-2 rounded-xl border border-primary/20 bg-white px-3 py-2 text-sm text-gray-700 shadow-lg dark:border-primary/30 dark:bg-gray-800 dark:text-gray-200"
      >
        <svg class="h-4 w-4 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        <span>Формирование сводного рейтинга...</span>
      </div>

      <div
        v-if="exporting"
        key="exporting-toast"
        class="flex items-center gap-2 rounded-xl border border-primary/20 bg-white px-3 py-2 text-sm text-gray-700 shadow-lg dark:border-primary/30 dark:bg-gray-800 dark:text-gray-200"
      >
        <svg class="h-4 w-4 animate-spin text-primary" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4" />
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
        </svg>
        <span>Подготовка Excel-файла...</span>
      </div>
    </transition-group>
  </div>
</template>
