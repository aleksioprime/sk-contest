<script setup>
/** Карточка заявки для модератора: заявитель, содержимое, файлы и решение. */
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  APP_STATUS_LABELS,
  APP_STATUS_TONES,
  DECISION_ACTIONS,
  SOURCE_LABELS,
  decide,
  fetchApplication,
  resendInvitation,
} from '@/api/applications'
import { errorMessage } from '@/api/http'
import ApplicantPanel from '@/components/events/ApplicantPanel.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'

const props = defineProps({
  applicationId: { type: Number, required: true },
  eventId: { type: Number, required: true },
  fields: { type: Array, default: () => [] },
})
const emit = defineEmits(['decided', 'close'])

const app = ref(null)
const comment = ref('')
const error = ref('')
const busy = ref('')

const notice = ref('')
const actions = computed(() => (app.value?.allowed_decisions ?? []).map((status) => ({ status, ...DECISION_ACTIONS[status] })))
const rawEntries = computed(() => Object.entries(app.value?.raw_payload ?? {}))
const participants = computed(() => app.value.members.filter((m) => m.role === 'participant'))
const supervisors = computed(() => app.value.members.filter((m) => m.role === 'supervisor'))

function answer(field) {
  const value = app.value.answers[field.key]
  if (field.type === 'file') return null
  if (typeof value === 'boolean') return value ? 'Да' : 'Нет'
  if (Array.isArray(value)) return value.join(', ')
  return value ?? '—'
}

async function load() {
  error.value = ''
  app.value = null
  try {
    app.value = await fetchApplication(props.applicationId)
    comment.value = ''
  } catch (e) {
    error.value = errorMessage(e)
  }
}

function onApplicantChanged(updated) {
  app.value = updated
  emit('decided', updated)
}

async function apply(status) {
  busy.value = status
  error.value = ''
  notice.value = ''
  try {
    app.value = await decide(app.value.id, status, comment.value)
    comment.value = ''
    if (status === 'confirmed') {
      notice.value = app.value.status === 'draft' ? `Приглашение отправлено на ${app.value.applicant_email}` : 'Заявка подтверждена и принята'
    }
    emit('decided', app.value)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = ''
  }
}

async function invite() {
  busy.value = 'invite'
  error.value = ''
  notice.value = ''
  try {
    app.value = await resendInvitation(app.value.id)
    notice.value = `Приглашение отправлено на ${app.value.applicant_email}`
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = ''
  }
}

watch(() => props.applicationId, load, { immediate: true })
</script>

<template>
  <section class="rounded-card border border-brand-200 bg-surface p-5" aria-label="Заявка">
    <SkeletonTable v-if="!app && !error" :rows="4" :columns="2" />
    <template v-if="app">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="text-lg font-semibold">№{{ app.number }} · {{ app.title || 'Без названия' }}</h2>
            <UiBadge :tone="APP_STATUS_TONES[app.status]">{{ APP_STATUS_LABELS[app.status] }}</UiBadge>
          </div>
          <p class="text-sm text-ink-muted">
            {{ [app.direction?.title, app.participation_form?.title, SOURCE_LABELS[app.source]].filter(Boolean).join(' · ') }}
          </p>
        </div>
        <div class="flex gap-1">
          <RouterLink
            :to="{ name: 'application', params: { id: app.id }, query: { manage: '1' } }"
            class="inline-flex h-8 items-center rounded-control px-3 text-sm text-brand-700 hover:bg-brand-50"
          >
            Редактировать
          </RouterLink>
          <UiButton size="sm" variant="ghost" @click="emit('close')">Закрыть</UiButton>
        </div>
      </div>

      <ApplicantPanel :key="app.id" class="mt-4" :application="app" :event-id="eventId" @changed="onApplicantChanged" />

      <dl class="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[180px_1fr]">
        <dt class="text-ink-muted">Участники</dt>
        <dd>
          <p v-for="m in participants" :key="m.id">
            {{ m.full_name }}<span v-if="m.grade" class="text-ink-muted">, {{ m.grade }} класс</span><span v-if="m.organization" class="text-ink-muted">, {{ m.organization }}</span>
          </p>
          <p v-if="!participants.length">—</p>
        </dd>
        <dt class="text-ink-muted">Руководители</dt>
        <dd>
          <p v-for="m in supervisors" :key="m.id">{{ m.full_name }} <span class="text-ink-muted">{{ m.email }}</span></p>
          <p v-if="!supervisors.length">—</p>
        </dd>
        <template v-for="field in fields.filter((f) => f.type !== 'file')" :key="field.key">
          <dt class="text-ink-muted">{{ field.label }}</dt>
          <dd class="whitespace-pre-line">{{ answer(field) }}</dd>
        </template>
        <dt class="text-ink-muted">Файлы</dt>
        <dd>
          <a v-for="file in app.files" :key="file.id" :href="file.url" target="_blank" class="block text-brand-700 hover:underline">{{ file.name }}</a>
          <p v-if="!app.files.length">—</p>
        </dd>
        <dt class="text-ink-muted">Согласия</dt>
        <dd>
          <p v-for="c in app.consents" :key="c.key">{{ c.title }}, версия {{ c.version }}, {{ new Date(c.accepted_at).toLocaleString('ru-RU') }}</p>
          <p v-if="!app.consents.length">—</p>
        </dd>
      </dl>

      <details v-if="rawEntries.length" class="mt-4 text-sm">
        <summary class="cursor-pointer font-medium">Исходные данные из внешней формы</summary>
        <dl class="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-[180px_1fr]">
          <template v-for="[key, value] in rawEntries" :key="key">
            <dt class="text-ink-muted">{{ key }}</dt>
            <dd class="break-words">{{ value }}</dd>
          </template>
        </dl>
      </details>

      <div v-if="actions.length || app.status === 'draft'" class="mt-5 grid gap-3 border-t border-line pt-4">
        <p v-if="app.moderator_comment" class="text-sm text-ink-muted">Прошлый комментарий: {{ app.moderator_comment }}</p>
        <label class="grid gap-1.5 text-sm">
          <span class="font-medium">Комментарий для участника</span>
          <textarea v-model="comment" rows="3" class="rounded-control border border-line bg-surface px-3 py-2" placeholder="Обязателен при возврате на доработку и отклонении" />
        </label>
        <div class="flex flex-wrap gap-2">
          <UiButton v-for="a in actions" :key="a.status" size="sm" :variant="a.variant" :loading="busy === a.status" @click="apply(a.status)">
            {{ a.label }}
          </UiButton>
          <UiButton v-if="app.status === 'draft'" size="sm" :loading="busy === 'invite'" @click="invite">Отправить приглашение ещё раз</UiButton>
        </div>
      </div>
      <p v-if="notice" role="status" class="mt-3 text-sm text-green-800">{{ notice }}</p>
    </template>
    <p v-if="error" role="alert" class="mt-3 text-sm text-red-700">{{ error }}</p>
  </section>
</template>
