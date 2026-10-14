<script setup>
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { APP_STATUS_LABELS, APP_STATUS_TONES, fetchMyApplications } from '@/api/applications'
import { errorMessage } from '@/api/http'
import { AWARD_LABELS, AWARD_TONES, fetchMyResults } from '@/api/stages'
import UiBadge from '@/components/ui/UiBadge.vue'
import SkeletonList from '@/components/skeleton/SkeletonList.vue'

const apps = ref([])
const resultsById = ref({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [list, results] = await Promise.all([fetchMyApplications(), fetchMyResults()])
    apps.value = list
    resultsById.value = Object.fromEntries(results.map((r) => [r.application_id, r]))
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="grid gap-6">
    <h1 class="text-2xl font-bold">Мои заявки</h1>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <SkeletonList v-else-if="loading" />
    <div v-else-if="!apps.length" class="rounded-card border border-dashed border-line bg-surface p-10 text-center">
      <h2 class="text-lg font-semibold">Заявок пока нет</h2>
      <p class="mt-1 text-ink-muted">Подать заявку можно на странице мероприятия, кнопкой «Подать заявку».</p>
    </div>
    <ul v-else class="grid gap-3">
      <li v-for="app in apps" :key="app.id">
        <RouterLink
          :to="{ name: 'application', params: { id: app.id } }"
          class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold">{{ app.title || 'Без названия' }}</p>
            <p class="text-sm text-ink-muted">{{ app.event.title }} · заявка №{{ app.number }}</p>
          </div>
          <UiBadge v-if="resultsById[app.id]" :tone="AWARD_TONES[resultsById[app.id].award]">
            {{ AWARD_LABELS[resultsById[app.id].award] }}<template v-if="resultsById[app.id].award !== 'participant'"> · {{ resultsById[app.id].rank }} место</template>
          </UiBadge>
          <span v-if="app.status === 'needs_changes'" class="text-sm text-amber-800">Внесите правки</span>
          <UiBadge :tone="APP_STATUS_TONES[app.status]">{{ APP_STATUS_LABELS[app.status] }}</UiBadge>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
