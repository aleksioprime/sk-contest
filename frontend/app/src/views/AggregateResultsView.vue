<!--
  Сводный рейтинг работ по нескольким оценочным листам (Viewer/Admin).
  Построение выполняется на фронтенде "на лету":
    1) выбор листов;
    2) опционально выбор отдельных работ;
    3) формирование общей таблицы с местами.
-->
<script setup>
import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import * as XLSX from 'xlsx'
import api from '../api'

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
const exporting = ref(false)

const worksBySheet = reactive({})      // { [sheetId]: work[] }
const loadedWorksBySheet = reactive({}) // { [sheetId]: true }
const loadingSheetWorks = reactive({}) // { [sheetId]: boolean }
const scorecardMaxScore = reactive({}) // { [scorecardId]: number }

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
  const rows = workRows.value.map((row) => {
    const rawScore = row.work.score != null ? Number(row.work.score) : null
    const maxScore = getSheetMaxScore(row.sheet)
    const normalizedScore = rawScore != null
      ? (maxScore > 0 ? (rawScore / maxScore) * 100 : rawScore)
      : null
    const metric = useNormalizedScore.value
      ? (normalizedScore != null ? normalizedScore : Number.NEGATIVE_INFINITY)
      : (rawScore != null ? rawScore : Number.NEGATIVE_INFINITY)

    return {
      ...row,
      rawScore,
      normalizedScore,
      metric,
      rank: null,
    }
  })

  const scoredRows = rows
    .filter((row) => row.rawScore != null && !Number.isNaN(row.rawScore))
    .sort((a, b) => {
      const diff = b.metric - a.metric
      if (diff !== 0) return diff
      return getWorkTitle(a.work).localeCompare(getWorkTitle(b.work), 'ru')
    })

  let previousMetric = null
  let previousRank = null
  for (let i = 0; i < scoredRows.length; i++) {
    const row = scoredRows[i]
    if (previousMetric == null || Math.abs(row.metric - previousMetric) > 1e-9) {
      row.rank = i + 1
      previousRank = row.rank
      previousMetric = row.metric
    } else {
      row.rank = previousRank
    }
  }

  const unscoredRows = rows
    .filter((row) => row.rawScore == null || Number.isNaN(row.rawScore))
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

onMounted(() => {
  loadSheets()
})

async function loadSheets() {
  loadingSheets.value = true
  error.value = ''
  try {
    const { data } = await api.get('/contest_evaluation_sheets:list', {
      params: {
        appends: 'contest,stage',
        pageSize: 500,
      },
    })
    sheets.value = (data.data || [])
      .filter((sheet) => {
        const status = sheet.status || 'inactive'
        return status === 'active' || status === 'inactive'
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
            appends: 'stage_participation,stage_participation.participation,stage_participation.participation.participants,stage_participation.participation.supervisors',
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
    { key: 'rank', title: 'Место', min: 8, max: 12 },
    { key: 'workTitle', title: 'Работа', min: 28, max: 60 },
    { key: 'participants', title: 'Участники', min: 30, max: 70 },
    { key: 'supervisors', title: 'Супервайзеры', min: 30, max: 70 },
    { key: 'rawScore', title: 'Балл', min: 10, max: 16 },
  ]
  if (useNormalizedScore.value) {
    cols.push({ key: 'normalizedScore', title: 'Нормализованный балл (0-100)', min: 20, max: 30 })
  }
  return cols
}

function getExportRows() {
  return rankedRows.value.map((row) => ({
    rank: row.rank ?? '',
    workTitle: getWorkTitle(row.work),
    participants: getParticipantNames(row.work) || '—',
    supervisors: getSupervisorNames(row.work) || '—',
    rawScore: row.rawScore != null ? Number(row.rawScore.toFixed(2)) : '',
    normalizedScore: useNormalizedScore.value && row.normalizedScore != null
      ? Number(row.normalizedScore.toFixed(2))
      : '',
  }))
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
    return { wch: Math.max(column.min, Math.min(column.max, padded)) }
  })
}

function toExcelCell(rowNumber, colNumber) {
  return `${XLSX.utils.encode_col(colNumber)}${rowNumber}`
}

function getExportMetaLine() {
  const now = new Date()
  const dt = now.toLocaleString('ru-RU')
  return `Сформировано: ${dt}`
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
    const columns = getExportColumns()
    const rows = getExportRows()
    const title = 'Сводный рейтинг конкурсных работ'
    const meta = getExportMetaLine()
    const headerRow = 4
    const dataStartRow = headerRow + 1
    const lastCol = columns.length - 1

    const worksheet = {}

    XLSX.utils.sheet_add_aoa(worksheet, [[title]], { origin: 'A1' })
    XLSX.utils.sheet_add_aoa(worksheet, [[meta]], { origin: 'A2' })
    XLSX.utils.sheet_add_aoa(worksheet, [columns.map((c) => c.title)], { origin: `A${headerRow}` })
    XLSX.utils.sheet_add_json(worksheet, rows, {
      origin: `A${dataStartRow}`,
      skipHeader: true,
      header: columns.map((c) => c.key),
    })

    worksheet['!cols'] = buildColumnWidths(columns, rows)
    worksheet['!merges'] = [
      { s: { r: 0, c: 0 }, e: { r: 0, c: lastCol } },
      { s: { r: 1, c: 0 }, e: { r: 1, c: lastCol } },
    ]

    const lastDataRow = dataStartRow + rows.length - 1
    const hasDataRows = rows.length > 0
    if (hasDataRows) {
      worksheet['!autofilter'] = {
        ref: `${toExcelCell(headerRow, 0)}:${toExcelCell(lastDataRow, lastCol)}`,
      }
    }

    // Числовой формат столбцов с баллами
    const rawScoreIdx = columns.findIndex((col) => col.key === 'rawScore')
    const normalizedScoreIdx = columns.findIndex((col) => col.key === 'normalizedScore')

    for (let i = 0; i < rows.length; i++) {
      const excelRow = dataStartRow + i
      if (rawScoreIdx >= 0) {
        const cell = worksheet[toExcelCell(excelRow, rawScoreIdx)]
        if (cell && typeof cell.v === 'number') cell.z = '0.00'
      }
      if (normalizedScoreIdx >= 0) {
        const cell = worksheet[toExcelCell(excelRow, normalizedScoreIdx)]
        if (cell && typeof cell.v === 'number') cell.z = '0.00'
      }
    }

    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, worksheet, 'Сводный рейтинг')
    XLSX.writeFile(workbook, getExportFileName())
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
        <p v-if="useNormalizedScore" class="text-xs text-gray-500 dark:text-gray-400">
          Итоговый ранг считается по нормализованному баллу.
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
                  <div class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ getWorkTitle(work) }}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">
                    Участники: {{ getParticipants(work).map((p) => p.full_name || p.short_name).join(', ') || '—' }}
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
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Место</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Работа</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Супервайзеры</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Лист</th>
                <th class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500">Балл</th>
                <th
                  v-if="useNormalizedScore"
                  class="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-gray-500"
                >
                  Норм. балл
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in rankedRows"
                :key="`${row.sheetId}-${row.id}`"
                class="border-b border-gray-100 last:border-b-0 dark:border-gray-700"
              >
                <td class="px-3 py-2 text-sm font-semibold text-gray-700 dark:text-gray-200">
                  {{ row.rank ?? '—' }}
                </td>
                <td class="px-3 py-2">
                  <div class="text-sm font-medium text-gray-900 dark:text-gray-100">{{ getWorkTitle(row.work) }}</div>
                  <div class="text-xs text-gray-500 dark:text-gray-400">
                    {{ getParticipants(row.work).map((p) => p.full_name || p.short_name).join(', ') || '—' }}
                  </div>
                </td>
                <td class="px-3 py-2 text-sm text-gray-600 dark:text-gray-300">
                  {{ getSupervisors(row.work).map((s) => s.full_name || s.short_name).join(', ') || '—' }}
                </td>
                <td class="px-3 py-2 text-sm text-gray-600 dark:text-gray-300">
                  {{ row.sheet.title }}
                </td>
                <td class="px-3 py-2 text-sm font-semibold text-score">
                  {{ formatScore(row.rawScore) }}
                </td>
                <td v-if="useNormalizedScore" class="px-3 py-2 text-sm font-semibold text-primary">
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
