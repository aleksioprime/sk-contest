<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { ROLE_LABELS, STATUS_LABELS, STATUS_TONES, fetchEvents } from '@/api/events'
import { errorMessage } from '@/api/http'
import UiBadge from '@/components/ui/UiBadge.vue'
import { useAuthStore } from '@/stores/auth'
import { formatRange } from '@/utils/dates'

const auth = useAuthStore()
const events = ref([])
const loading = ref(true)
const error = ref('')
const scope = ref('mine')

const canCreate = computed(() => auth.isAdmin || auth.user?.person?.is_employee)

async function load() {
  loading.value = true
  error.value = ''
  try {
    events.value = await fetchEvents(scope.value)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function dates(event) {
  return formatRange(event.date_start, event.date_end) || 'Даты не указаны'
}

watch(scope, load)
onMounted(load)
</script>

<template>
  <div class="grid gap-6">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <h1 class="text-2xl font-bold">Мероприятия</h1>
      <div class="flex items-center gap-3">
        <select v-if="auth.isAdmin" v-model="scope" aria-label="Какие мероприятия показать" class="h-10 rounded-control border border-line bg-surface px-3 text-sm">
          <option value="mine">Мои</option>
          <option value="all">Все</option>
        </select>
        <RouterLink
          v-if="canCreate"
          :to="{ name: 'event-new' }"
          class="inline-flex h-10 items-center rounded-control bg-brand-600 px-4 font-medium text-white hover:bg-brand-700"
        >
          Создать мероприятие
        </RouterLink>
      </div>
    </div>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-else-if="loading" class="text-ink-muted">Загрузка…</p>

    <div v-else-if="!events.length" class="rounded-card border border-dashed border-line bg-surface p-10 text-center">
      <h2 class="text-lg font-semibold">Здесь появятся ваши мероприятия</h2>
      <p class="mt-1 text-ink-muted">
        {{ canCreate ? 'Создайте первое мероприятие из готового шаблона.' : 'Когда вас добавят в команду мероприятия, оно появится в этом списке.' }}
      </p>
    </div>

    <ul v-else class="grid gap-3">
      <li v-for="event in events" :key="event.id">
        <RouterLink
          :to="{ name: 'event', params: { id: event.id } }"
          class="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-card border border-line bg-surface p-4 hover:border-brand-200"
        >
          <div class="min-w-0 flex-1">
            <p class="truncate font-semibold">{{ event.title }}</p>
            <p class="text-sm text-ink-muted">{{ dates(event) }} · {{ event.slug }}</p>
          </div>
          <div class="flex flex-wrap gap-1.5">
            <UiBadge v-for="role in event.my_roles" :key="role">{{ ROLE_LABELS[role] }}</UiBadge>
            <UiBadge :tone="STATUS_TONES[event.status]">{{ STATUS_LABELS[event.status] }}</UiBadge>
          </div>
        </RouterLink>
      </li>
    </ul>
  </div>
</template>
