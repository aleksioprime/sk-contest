<script setup>
/** Кабинет участника: мои заявки, результаты и мероприятия с открытым приёмом. */
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { APP_STATUS_LABELS, APP_STATUS_TONES, fetchMyApplications, fetchOpenEvents } from '@/api/applications'
import { errorMessage, SkeletonList, UiBadge } from 'sk-ui'
import { AWARD_LABELS, AWARD_TONES, fetchMyResults } from '@/api/stages'
import { formatRange } from '@/utils/dates'

const apps = ref([])
const openEvents = ref([])
const resultsById = ref({})
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    const [list, results, events] = await Promise.all([fetchMyApplications(), fetchMyResults(), fetchOpenEvents()])
    apps.value = list
    openEvents.value = events
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
      <p class="mt-1 text-ink-muted">Мероприятия с открытым приёмом заявок появятся на этой странице.</p>
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
          <UiBadge v-for="n in resultsById[app.id]?.nominations ?? []" :key="n" tone="warning">{{ n }}</UiBadge>
          <span v-if="app.status === 'needs_changes'" class="text-sm text-amber-800">Внесите правки</span>
          <span v-else-if="app.status === 'draft' && app.can_edit" class="text-sm text-brand-700">Заполните заявку</span>
          <UiBadge :tone="APP_STATUS_TONES[app.status]">{{ APP_STATUS_LABELS[app.status] }}</UiBadge>
        </RouterLink>
      </li>
    </ul>

    <section v-if="openEvents.length" class="grid gap-3">
      <h2 class="text-lg font-semibold">Открыт приём заявок</h2>
      <ul class="grid gap-3 sm:grid-cols-2">
        <li v-for="event in openEvents" :key="event.slug">
          <RouterLink :to="{ name: 'apply', params: { slug: event.slug } }" class="block rounded-card border border-line bg-surface p-4 hover:border-brand-200">
            <p class="font-semibold">{{ event.title }}</p>
            <p v-if="event.date_start" class="text-sm text-ink-muted">{{ formatRange(event.date_start, event.date_end) }}</p>
            <p v-if="event.short_description" class="mt-1 text-sm">{{ event.short_description }}</p>
            <p class="mt-2 text-sm font-medium text-brand-700">Подать заявку →</p>
          </RouterLink>
        </li>
      </ul>
    </section>
  </div>
</template>
