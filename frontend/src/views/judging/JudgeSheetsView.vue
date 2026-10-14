<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { SHEET_STATUS_LABELS, SHEET_STATUS_TONES, fetchMySheets } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import UiBadge from '@/components/ui/UiBadge.vue'

const sheets = ref([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    sheets.value = await fetchMySheets()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="grid gap-6">
    <h1 class="text-2xl font-bold">Оценивание</h1>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-else-if="loading" class="text-ink-muted">Загрузка…</p>
    <div v-else-if="!sheets.length" class="rounded-card border border-dashed border-line bg-surface p-10 text-center">
      <h2 class="text-lg font-semibold">Работ для оценки пока нет</h2>
      <p class="mt-1 text-ink-muted">Когда организаторы запустят оценочный лист с вашим участием, он появится здесь.</p>
    </div>
    <ul v-else class="grid gap-3">
      <li v-for="sheet in sheets" :key="sheet.id">
        <RouterLink
          :to="{ name: 'judge-sheet', params: { id: sheet.id } }"
          class="grid gap-3 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <div class="flex flex-wrap items-center gap-3">
            <div class="min-w-0 flex-1">
              <p class="font-semibold">{{ sheet.title }}</p>
              <p class="text-sm text-ink-muted">{{ sheet.event_title }}</p>
            </div>
            <UiBadge :tone="SHEET_STATUS_TONES[sheet.status]">{{ SHEET_STATUS_LABELS[sheet.status] }}</UiBadge>
          </div>
          <div class="flex items-center gap-3 text-sm">
            <div class="h-2 flex-1 overflow-hidden rounded-full bg-canvas" role="progressbar" :aria-valuenow="sheet.scored" :aria-valuemax="sheet.total">
              <div class="h-full rounded-full bg-brand-600" :style="{ width: `${sheet.total ? (100 * sheet.scored) / sheet.total : 0}%` }" />
            </div>
            <span class="tabular-nums text-ink-muted">{{ sheet.scored }} из {{ sheet.total }}</span>
          </div>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
