<script setup>
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { fetchMySheets, fetchMyWorks, formatPoints } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import UiBadge from '@/components/ui/UiBadge.vue'
import SkeletonList from '@/components/skeleton/SkeletonList.vue'

const props = defineProps({ id: { type: String, required: true } })
const works = ref([])
const sheet = ref(null)
const sheetsCount = ref(0)
const error = ref('')
const loading = ref(true)
const left = computed(() => works.value.filter((w) => !w.is_scored).length)

onMounted(async () => {
  try {
    const [list, sheets] = await Promise.all([fetchMyWorks(props.id), fetchMySheets()])
    works.value = list
    sheet.value = sheets.find((s) => String(s.id) === String(props.id)) ?? null
    sheetsCount.value = sheets.length
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="grid gap-6">
    <div>
      <RouterLink v-if="sheetsCount > 1" :to="{ name: 'judging' }" class="text-sm text-ink-muted hover:text-ink">← Все листы</RouterLink>
      <p v-if="sheet" class="mt-2 text-sm text-ink-muted">{{ sheet.event_title }}</p>
      <h1 class="text-2xl font-bold">{{ sheet?.title ?? 'Работы для оценки' }}</h1>
      <p v-if="!loading && works.length" class="mt-1 text-ink-muted">{{ left ? `Осталось оценить: ${left}` : 'Все работы оценены' }}</p>
    </div>
    <p v-if="sheet && !sheet.editable" class="rounded-control bg-amber-50 px-4 py-3 text-amber-900">
      Оценка закрыта модератором. Выставленные баллы можно посмотреть, но не изменить.
    </p>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <SkeletonList v-else-if="loading" :rows="5" />
    <ol v-else class="grid gap-2">
      <li v-for="work in works" :key="work.evaluation_id">
        <RouterLink
          :to="{ name: 'judge-evaluation', params: { id: work.evaluation_id } }"
          class="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <span class="w-8 text-sm tabular-nums text-ink-muted">№{{ work.number }}</span>
          <div class="min-w-0 flex-1">
            <p class="font-medium">{{ work.title || 'Без названия' }}</p>
            <p class="text-sm text-ink-muted">{{ work.participants.join(', ') }}<span v-if="work.direction"> · {{ work.direction }}</span></p>
          </div>
          <span class="tabular-nums font-semibold text-score-600">{{ formatPoints(work.score) }}</span>
          <UiBadge :tone="work.is_scored ? 'success' : work.score !== null ? 'warning' : 'neutral'">
            {{ work.is_scored ? 'оценено' : work.score !== null ? 'не все критерии' : 'не начато' }}
          </UiBadge>
        </RouterLink>
      </li>
    </ol>
  </div>
</template>
