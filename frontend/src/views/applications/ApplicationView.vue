<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import {
  APP_STATUS_LABELS,
  APP_STATUS_TONES,
  fetchApplication,
  fetchPublicForm,
  fieldErrors,
  isVisible,
  saveApplication,
  submitApplication,
  withdrawApplication,
} from '@/api/applications'
import { errorMessage } from '@/api/http'
import FieldInput from '@/components/applications/FieldInput.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'

const props = defineProps({ id: { type: String, required: true } })

const app = ref(null)
const schema = ref(null)
const draft = reactive({ title: '', direction_id: null, participation_form_id: null, answers: {}, members: [], consents: [] })
const errors = ref({})
const message = ref('')
const notice = ref('')
const busy = ref('')
const confirmWithdraw = ref(false)

const form = computed(() => schema.value?.form ?? { fields: [], team: {}, consents: [] })
const editable = computed(() => !!app.value?.can_edit)
const participants = computed(() => draft.members.filter((m) => m.role === 'participant'))
const supervisors = computed(() => draft.members.filter((m) => m.role === 'supervisor'))
const maxParticipants = computed(() => (form.value.team.enabled ? form.value.team.max : 1))
const visibleFields = computed(() => form.value.fields.filter((f) => isVisible(f, draft.answers)))

function fill(data) {
  app.value = data
  Object.assign(draft, {
    title: data.title,
    direction_id: data.direction?.id ?? null,
    participation_form_id: data.participation_form?.id ?? null,
    answers: { ...data.answers },
    members: data.members.map(({ role, full_name, email, grade, organization }) => ({ role, full_name, email, grade, organization })),
    consents: data.consents.map((c) => c.key),
  })
}

async function load() {
  message.value = ''
  try {
    const data = await fetchApplication(props.id)
    schema.value = await fetchPublicForm(data.event.slug)
    fill(data)
  } catch (e) {
    message.value = errorMessage(e)
  }
}

function addMember(role) {
  draft.members.push({ role, full_name: '', email: '', grade: '', organization: '' })
}

function removeMember(member) {
  draft.members.splice(draft.members.indexOf(member), 1)
}

function payload() {
  const answers = Object.fromEntries(
    Object.entries(draft.answers).filter(([key, value]) => value !== '' && value !== null && form.value.fields.some((f) => f.key === key)),
  )
  return { ...draft, members: draft.members.filter((m) => m.full_name.trim()), answers }
}

async function run(action, fn) {
  busy.value = action
  errors.value = {}
  message.value = ''
  notice.value = ''
  try {
    fill(await fn())
    return true
  } catch (e) {
    errors.value = fieldErrors(e)
    message.value = errorMessage(e)
    return false
  } finally {
    busy.value = ''
  }
}

async function save() {
  if (await run('save', () => saveApplication(app.value.id, payload()))) notice.value = 'Черновик сохранён'
}

async function submit() {
  const saved = await run('submit', () => saveApplication(app.value.id, payload()))
  if (saved && (await run('submit', () => submitApplication(app.value.id)))) {
    notice.value = 'Заявка отправлена. Мы пришлём письмо, когда организаторы её рассмотрят.'
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
}

async function withdraw() {
  confirmWithdraw.value = false
  await run('withdraw', () => withdrawApplication(app.value.id))
}

watch(() => props.id, load, { immediate: true })
</script>

<template>
  <p v-if="!app && message" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ message }}</p>
  <SkeletonPage v-else-if="!app" :cards="3" class="max-w-3xl" />

  <div v-else class="grid max-w-3xl gap-6">
    <div>
      <RouterLink :to="{ name: 'my-applications' }" class="text-sm text-ink-muted hover:text-ink">← Мои заявки</RouterLink>
      <div class="mt-2 flex flex-wrap items-center gap-2">
        <h1 class="text-2xl font-bold">Заявка №{{ app.number }}</h1>
        <UiBadge :tone="APP_STATUS_TONES[app.status]">{{ APP_STATUS_LABELS[app.status] }}</UiBadge>
      </div>
      <p class="mt-1 text-ink-muted">{{ app.event.title }}</p>
    </div>

    <p v-if="notice" role="status" class="rounded-control bg-green-100 px-4 py-3 text-green-800">{{ notice }}</p>
    <div v-if="app.moderator_comment && app.status !== 'draft'" class="rounded-card border border-amber-300 bg-amber-50 p-4 text-amber-900">
      <p class="font-semibold">Комментарий организаторов</p>
      <p class="mt-1 whitespace-pre-line">{{ app.moderator_comment }}</p>
    </div>
    <p v-if="app.status === 'draft' && !editable" class="rounded-control bg-canvas px-4 py-3 text-ink-muted">
      Приём заявок закрыт, черновик больше нельзя отправить.
    </p>

    <form class="grid gap-6" novalidate @submit.prevent="submit">
      <fieldset :disabled="!editable" class="grid gap-6">
        <UiCard>
          <template #title>Работа</template>
          <div class="grid gap-4">
            <UiInput v-model="draft.title" label="Название работы" :error="errors.title" />
            <label v-if="schema.directions.length" class="grid gap-1.5 text-sm">
              <span class="font-medium">Направление</span>
              <select v-model="draft.direction_id" class="h-10 rounded-control border bg-surface px-3" :class="errors.direction_id ? 'border-red-500' : 'border-line'">
                <option :value="null">Не выбрано</option>
                <option v-for="d in schema.directions" :key="d.id" :value="d.id">{{ d.title }}</option>
              </select>
              <span v-if="errors.direction_id" class="text-red-600">{{ errors.direction_id }}</span>
            </label>
            <label v-if="schema.participation_forms.length" class="grid gap-1.5 text-sm">
              <span class="font-medium">Форма участия</span>
              <select v-model="draft.participation_form_id" class="h-10 rounded-control border bg-surface px-3" :class="errors.participation_form_id ? 'border-red-500' : 'border-line'">
                <option :value="null">Не выбрано</option>
                <option v-for="f in schema.participation_forms" :key="f.id" :value="f.id">{{ f.title }}</option>
              </select>
              <span v-if="errors.participation_form_id" class="text-red-600">{{ errors.participation_form_id }}</span>
            </label>
          </div>
        </UiCard>

        <UiCard>
          <template #title>{{ maxParticipants > 1 ? 'Команда' : 'Участник' }}</template>
          <div class="grid gap-4">
            <div v-for="(member, index) in participants" :key="`p${index}`" class="grid gap-3 rounded-control border border-line p-3 sm:grid-cols-[2fr_1fr_2fr_auto]">
              <UiInput v-model="member.full_name" placeholder="Фамилия Имя Отчество" aria-label="ФИО участника" />
              <UiInput v-model="member.grade" placeholder="Класс" aria-label="Класс" />
              <UiInput v-model="member.organization" placeholder="Школа, если не Гимназия Сколково" aria-label="Школа" />
              <UiButton v-if="editable" size="sm" variant="ghost" @click="removeMember(member)">Убрать</UiButton>
            </div>
            <div v-if="editable && participants.length < maxParticipants">
              <UiButton size="sm" @click="addMember('participant')">Добавить участника</UiButton>
            </div>

            <template v-if="form.team.supervisors_max > 0">
              <p class="mt-2 font-medium">Руководитель<span v-if="form.team.require_supervisor" class="text-red-600" aria-hidden="true"> *</span></p>
              <div v-for="(member, index) in supervisors" :key="`s${index}`" class="grid gap-3 rounded-control border border-line p-3 sm:grid-cols-[2fr_2fr_auto]">
                <UiInput v-model="member.full_name" placeholder="Фамилия Имя Отчество" aria-label="ФИО руководителя" />
                <UiInput v-model="member.email" type="email" placeholder="Email" aria-label="Email руководителя" />
                <UiButton v-if="editable" size="sm" variant="ghost" @click="removeMember(member)">Убрать</UiButton>
              </div>
              <div v-if="editable && supervisors.length < form.team.supervisors_max">
                <UiButton size="sm" @click="addMember('supervisor')">Добавить руководителя</UiButton>
              </div>
            </template>
            <p v-if="errors.members" class="text-sm text-red-600">{{ errors.members }}</p>
          </div>
        </UiCard>

        <UiCard v-if="visibleFields.length">
          <template #title>Анкета</template>
          <div class="grid gap-5">
            <FieldInput
              v-for="field in visibleFields"
              :key="field.key"
              v-model="draft.answers[field.key]"
              :field="field"
              :error="errors[field.key]"
              :files="app.files"
              :disabled="!editable"
            />
          </div>
        </UiCard>

        <UiCard v-if="form.consents.length">
          <template #title>Согласия</template>
          <div class="grid gap-4">
            <div v-for="consent in form.consents" :key="consent.key">
              <label class="flex items-start gap-2">
                <input v-model="draft.consents" type="checkbox" :value="consent.key" class="mt-1 size-4 accent-brand-600" />
                <span class="font-medium">{{ consent.title }}<span v-if="consent.required" class="text-red-600" aria-hidden="true"> *</span></span>
              </label>
              <details class="ml-6 mt-1 text-sm text-ink-muted">
                <summary class="cursor-pointer">Текст согласия</summary>
                <p class="mt-1 whitespace-pre-line">{{ consent.text }}</p>
              </details>
              <p v-if="errors[`consent:${consent.key}`]" class="ml-6 text-sm text-red-600">{{ errors[`consent:${consent.key}`] }}</p>
            </div>
          </div>
        </UiCard>
      </fieldset>

      <p v-if="message" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ message }}</p>

      <div class="flex flex-wrap items-center gap-3">
        <template v-if="editable">
          <UiButton type="submit" variant="primary" :loading="busy === 'submit'">{{ app.status === 'needs_changes' ? 'Отправить повторно' : 'Отправить заявку' }}</UiButton>
          <UiButton :loading="busy === 'save'" @click="save">Сохранить черновик</UiButton>
        </template>
        <template v-if="app.can_withdraw">
          <UiButton v-if="!confirmWithdraw" variant="ghost" @click="confirmWithdraw = true">Отозвать заявку</UiButton>
          <span v-else class="flex flex-wrap items-center gap-2 text-sm">
            Отозвать заявку? Отменить это будет нельзя.
            <UiButton size="sm" variant="danger" :loading="busy === 'withdraw'" @click="withdraw">Отозвать</UiButton>
            <UiButton size="sm" variant="ghost" @click="confirmWithdraw = false">Отмена</UiButton>
          </span>
        </template>
      </div>
    </form>
  </div>
</template>
