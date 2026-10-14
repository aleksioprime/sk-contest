<script setup>
import { onMounted, reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import {
  SHEET_MODE_LABELS,
  SHEET_STATUS_LABELS,
  SHEET_STATUS_TONES,
  copyScorecard,
  createSheet,
  deleteScale,
  deleteScorecard,
  fetchScales,
  fetchScorecards,
  fetchSheets,
  formatPoints,
} from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import ScaleEditor from '@/components/evaluation/ScaleEditor.vue'
import ScorecardEditor from '@/components/evaluation/ScorecardEditor.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'

const props = defineProps({ event: { type: Object, required: true } })
const router = useRouter()

const sheets = ref([])
const scorecards = ref([])
const scales = ref([])
const error = ref('')
const loaded = ref(false)
const editingScale = ref(null) // объект шкалы или 'new'
const editingCard = ref(null)
const newSheet = reactive({ open: false, title: '', scorecard_id: null, stage_id: null, mode: 'jury' })
const sheetError = ref('')

async function load() {
  error.value = ''
  try {
    ;[sheets.value, scorecards.value, scales.value] = await Promise.all([
      fetchSheets(props.event.id),
      props.event.can_manage ? fetchScorecards(props.event.id) : [],
      props.event.can_manage ? fetchScales(props.event.id) : [],
    ])
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loaded.value = true
  }
}

async function run(fn) {
  error.value = ''
  try {
    await fn()
    await load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function submitSheet() {
  sheetError.value = ''
  if (!newSheet.title.trim() || !newSheet.scorecard_id) {
    sheetError.value = 'Укажите название и таблицу оценок'
    return
  }
  try {
    const sheet = await createSheet(props.event.id, {
      title: newSheet.title,
      scorecard_id: newSheet.scorecard_id,
      stage_id: newSheet.stage_id,
      mode: newSheet.mode,
    })
    await router.push({ name: 'event-sheet', params: { id: props.event.id, sheetId: sheet.id } })
  } catch (e) {
    sheetError.value = errorMessage(e)
  }
}

function onCardSaved() {
  editingCard.value = null
  load()
}

function onScaleSaved() {
  editingScale.value = null
  load()
}

onMounted(load)
</script>

<template>
  <div class="grid gap-6">
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <SkeletonPage v-if="!loaded" :cards="3" />

    <UiCard v-if="loaded">
      <template #title>Оценочные листы</template>
      <ul v-if="sheets.length" class="mb-4 divide-y divide-line">
        <li v-for="sheet in sheets" :key="sheet.id">
          <RouterLink :to="{ name: 'event-sheet', params: { id: event.id, sheetId: sheet.id } }" class="flex flex-wrap items-center gap-3 py-3 hover:text-brand-700">
            <span class="min-w-0 flex-1 font-medium">{{ sheet.title }}</span>
            <span class="text-sm text-ink-muted">{{ SHEET_MODE_LABELS[sheet.mode] }} · работ {{ sheet.works }} · судей {{ sheet.judges }} · оценено {{ sheet.progress }}%</span>
            <UiBadge :tone="SHEET_STATUS_TONES[sheet.status]">{{ SHEET_STATUS_LABELS[sheet.status] }}</UiBadge>
          </RouterLink>
        </li>
      </ul>
      <p v-else class="mb-4 text-sm text-ink-muted">Лист объединяет работы, судей и таблицу оценок. Обычно это один этап одного направления.</p>

      <form v-if="event.can_manage && newSheet.open" class="grid gap-3 rounded-control border border-brand-200 p-4" @submit.prevent="submitSheet">
        <input v-model="newSheet.title" placeholder="Например, Очная защита · Инженерия" aria-label="Название листа" class="h-10 rounded-control border border-line bg-surface px-3" />
        <div class="grid gap-3 sm:grid-cols-3">
          <select v-model="newSheet.scorecard_id" aria-label="Таблица оценок" class="h-10 rounded-control border border-line bg-surface px-3">
            <option :value="null">Таблица оценок…</option>
            <option v-for="card in scorecards" :key="card.id" :value="card.id">{{ card.title }}</option>
          </select>
          <select v-model="newSheet.stage_id" aria-label="Этап" class="h-10 rounded-control border border-line bg-surface px-3">
            <option :value="null">Без этапа</option>
            <option v-for="stage in event.stages" :key="stage.id" :value="stage.id">{{ stage.title }}</option>
          </select>
          <select v-model="newSheet.mode" aria-label="Кто оценивает" class="h-10 rounded-control border border-line bg-surface px-3">
            <option v-for="(label, value) in SHEET_MODE_LABELS" :key="value" :value="value">{{ label }}</option>
          </select>
        </div>
        <p v-if="!scorecards.length" class="text-sm text-amber-800">Сначала создайте таблицу оценок ниже.</p>
        <p v-if="sheetError" role="alert" class="text-sm text-red-700">{{ sheetError }}</p>
        <div class="flex gap-2">
          <UiButton type="submit" size="sm" variant="primary">Создать лист</UiButton>
          <UiButton size="sm" variant="ghost" @click="newSheet.open = false">Отмена</UiButton>
        </div>
      </form>
      <UiButton v-else-if="event.can_manage" variant="primary" size="sm" @click="newSheet.open = true">Новый лист</UiButton>
    </UiCard>

    <UiCard v-if="loaded && event.can_manage">
      <template #title>Таблицы оценок</template>
      <ScorecardEditor
        v-if="editingCard"
        :event-id="event.id"
        :scales="scales"
        :scorecard="editingCard === 'new' ? null : editingCard"
        @saved="onCardSaved"
        @cancel="editingCard = null"
      />
      <template v-else>
        <ul class="mb-4 divide-y divide-line">
          <li v-for="card in scorecards" :key="card.id" class="flex flex-wrap items-center gap-3 py-3">
            <div class="min-w-0 flex-1">
              <p class="font-medium">{{ card.title }}</p>
              <p class="text-sm text-ink-muted">Критериев {{ card.criteria.length }} · максимум {{ formatPoints(card.max_score) }}<span v-if="card.in_use"> · по ней уже оценивают</span></p>
            </div>
            <UiButton v-if="!card.in_use" size="sm" variant="ghost" @click="editingCard = card">Изменить</UiButton>
            <UiButton size="sm" variant="ghost" @click="run(() => copyScorecard(card.id))">Копировать</UiButton>
            <UiButton size="sm" variant="ghost" @click="run(() => deleteScorecard(card.id))">Удалить</UiButton>
          </li>
        </ul>
        <UiButton size="sm" @click="editingCard = 'new'">Новая таблица</UiButton>
      </template>
    </UiCard>

    <UiCard v-if="loaded && event.can_manage">
      <template #title>Шкалы</template>
      <ScaleEditor
        v-if="editingScale"
        :event-id="event.id"
        :scale="editingScale === 'new' ? null : editingScale"
        @saved="onScaleSaved"
        @cancel="editingScale = null"
      />
      <template v-else>
        <ul class="mb-4 divide-y divide-line">
          <li v-for="scale in scales" :key="scale.id" class="flex flex-wrap items-center gap-3 py-3">
            <div class="min-w-0 flex-1">
              <p class="font-medium">{{ scale.title }}</p>
              <p class="text-sm text-ink-muted">{{ scale.levels.map((l) => `${formatPoints(l.points)} — ${l.title}`).join(' · ') }}</p>
            </div>
            <UiButton size="sm" variant="ghost" @click="editingScale = scale">Изменить</UiButton>
            <UiButton size="sm" variant="ghost" @click="run(() => deleteScale(scale.id))">Удалить</UiButton>
          </li>
        </ul>
        <UiButton size="sm" @click="editingScale = 'new'">Новая шкала</UiButton>
      </template>
    </UiCard>
  </div>
</template>
