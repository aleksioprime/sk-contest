<script setup>
/** Карточка заявки для модератора: содержимое, файлы и решение. */
import { computed, ref, watch } from 'vue'
import { APP_STATUS_LABELS, APP_STATUS_TONES, decide, fetchApplication } from '@/api/applications'
import { errorMessage } from '@/api/http'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import SkeletonTable from '@/components/skeleton/SkeletonTable.vue'

const props = defineProps({
  applicationId: { type: Number, required: true },
  fields: { type: Array, default: () => [] },
})
const emit = defineEmits(['decided', 'close'])

const app = ref(null)
const comment = ref('')
const error = ref('')
const busy = ref('')

const ACTIONS = [
  { status: 'accepted', label: 'Принять', variant: 'primary' },
  { status: 'needs_changes', label: 'Вернуть на доработку', variant: 'secondary' },
  { status: 'rejected', label: 'Отклонить', variant: 'danger' },
  { status: 'submitted', label: 'Вернуть на рассмотрение', variant: 'ghost' },
]
const actions = computed(() =>
  ['draft', 'withdrawn'].includes(app.value?.status) ? [] : ACTIONS.filter((a) => a.status !== app.value?.status),
)

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
    comment.value = app.value.moderator_comment
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function apply(status) {
  busy.value = status
  error.value = ''
  try {
    app.value = await decide(app.value.id, status, comment.value)
    emit('decided', app.value)
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
            {{ app.direction?.title }}{{ app.participation_form ? ` · ${app.participation_form.title}` : '' }} · подал {{ app.applicant_name }}, {{ app.applicant_email }}
          </p>
        </div>
        <UiButton size="sm" variant="ghost" @click="emit('close')">Закрыть</UiButton>
      </div>

      <dl class="mt-4 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[180px_1fr]">
        <dt class="text-ink-muted">Участники</dt>
        <dd>
          <p v-for="m in app.members.filter((m) => m.role === 'participant')" :key="m.id">
            {{ m.full_name }}<span v-if="m.grade" class="text-ink-muted">, {{ m.grade }} класс</span><span v-if="m.organization" class="text-ink-muted">, {{ m.organization }}</span>
          </p>
        </dd>
        <dt class="text-ink-muted">Руководители</dt>
        <dd>
          <p v-for="m in app.members.filter((m) => m.role === 'supervisor')" :key="m.id">{{ m.full_name }} <span class="text-ink-muted">{{ m.email }}</span></p>
          <p v-if="!app.members.some((m) => m.role === 'supervisor')">—</p>
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
        </dd>
      </dl>

      <div v-if="actions.length" class="mt-5 grid gap-3 border-t border-line pt-4">
        <label class="grid gap-1.5 text-sm">
          <span class="font-medium">Комментарий для участника</span>
          <textarea v-model="comment" rows="3" class="rounded-control border border-line bg-surface px-3 py-2" placeholder="Обязателен при возврате на доработку и отклонении" />
        </label>
        <div class="flex flex-wrap gap-2">
          <UiButton v-for="a in actions" :key="a.status" size="sm" :variant="a.variant" :loading="busy === a.status" @click="apply(a.status)">
            {{ a.label }}
          </UiButton>
        </div>
      </div>
    </template>
    <p v-if="error" role="alert" class="mt-3 text-sm text-red-700">{{ error }}</p>
  </section>
</template>
