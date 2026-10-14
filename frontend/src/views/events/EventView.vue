<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  FORMAT_LABELS,
  LEVEL_LABELS,
  MODULE_LABELS,
  ROLE_LABELS,
  STATUS_LABELS,
  STATUS_TONES,
  addMember,
  changeStatus,
  deleteEvent,
  fetchEvent,
  fetchMembers,
  removeMember,
  updateEvent,
} from '@/api/events'
import { errorMessage } from '@/api/http'
import { uploadFile } from '@/api/applications'
import ApplicationsPanel from '@/components/events/ApplicationsPanel.vue'
import EvaluationPanel from '@/components/evaluation/EvaluationPanel.vue'
import EventItemsEditor from '@/components/events/EventItemsEditor.vue'
import FormBuilder from '@/components/events/FormBuilder.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'

const props = defineProps({ id: { type: String, required: true } })
const route = useRoute()
const router = useRouter()

const event = ref(null)
const loadError = ref('')
const form = reactive({})
const saving = ref(false)
const saveError = ref('')
const savedAt = ref(null)
const statusError = ref('')
const confirmDelete = ref(false)

const members = ref([])
const memberEmail = ref('')
const memberRole = ref('judge')
const memberError = ref('')

const tabs = computed(() => [
  { id: 'main', label: 'Основное' },
  { id: 'directions', label: 'Направления' },
  ...(event.value?.modules.stages ? [{ id: 'stages', label: 'Этапы' }] : []),
  { id: 'forms', label: 'Формы участия' },
  ...(event.value?.modules.registration && (event.value.can_manage || event.value.my_roles.includes('moderator'))
    ? [{ id: 'applications', label: 'Заявки' }]
    : []),
  ...(event.value?.modules.registration && event.value.can_manage ? [{ id: 'form', label: 'Анкета' }] : []),
  ...(event.value?.modules.evaluation && event.value.can_manage ? [{ id: 'evaluation', label: 'Оценивание' }] : []),
  { id: 'team', label: 'Команда' },
])
const tab = computed({
  get: () => (tabs.value.some((t) => t.id === route.query.tab) ? route.query.tab : 'main'),
  set: (value) => router.replace({ query: { ...route.query, tab: value } }),
})
const readonly = computed(() => !event.value?.can_manage)

const STATUS_ACTIONS = {
  draft: 'Вернуть в черновик',
  registration: 'Открыть регистрацию',
  running: 'Начать мероприятие',
  results: 'Перейти к итогам',
  archived: 'Отправить в архив',
}
const FIELDS = [
  'title', 'slug', 'short_description', 'description', 'level', 'format', 'place',
  'date_start', 'date_end', 'registration_opens_at', 'registration_closes_at',
]

/** Значение для поля datetime-local в местном времени пользователя. */
function toLocalInput(value) {
  if (!value) return ''
  const date = new Date(value)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function fillForm(data) {
  for (const key of FIELDS) form[key] = data[key] ?? ''
  form.registration_opens_at = toLocalInput(data.registration_opens_at)
  form.registration_closes_at = toLocalInput(data.registration_closes_at)
  form.modules = { ...data.modules }
}

async function load() {
  loadError.value = ''
  try {
    event.value = await fetchEvent(props.id)
    fillForm(event.value)
    members.value = await fetchMembers(props.id)
  } catch (e) {
    loadError.value = errorMessage(e)
  }
}

async function save() {
  saving.value = true
  saveError.value = ''
  try {
    const changes = { ...form }
    for (const key of ['date_start', 'date_end', 'registration_opens_at', 'registration_closes_at']) {
      changes[key] = changes[key] ? (key.startsWith('registration') ? new Date(changes[key]).toISOString() : changes[key]) : null
    }
    event.value = await updateEvent(event.value.id, changes)
    fillForm(event.value)
    savedAt.value = new Date()
  } catch (e) {
    saveError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

const coverError = ref('')
const coverUploading = ref(false)

async function setCover(file) {
  coverError.value = ''
  coverUploading.value = true
  try {
    const cover_file_id = file ? (await uploadFile(file, 'image')).id : null
    event.value = await updateEvent(event.value.id, { cover_file_id })
  } catch (e) {
    coverError.value = errorMessage(e)
  } finally {
    coverUploading.value = false
  }
}

async function setStatus(status) {
  statusError.value = ''
  try {
    event.value = await changeStatus(event.value.id, status)
  } catch (e) {
    statusError.value = errorMessage(e)
  }
}

async function remove() {
  try {
    await deleteEvent(event.value.id)
    await router.push({ name: 'events' })
  } catch (e) {
    statusError.value = errorMessage(e)
  }
}

async function invite() {
  memberError.value = ''
  if (!/^\S+@\S+\.\S+$/.test(memberEmail.value.trim())) {
    memberError.value = 'Введите адрес электронной почты'
    return
  }
  try {
    await addMember(event.value.id, memberEmail.value.trim(), memberRole.value)
    members.value = await fetchMembers(event.value.id)
    memberEmail.value = ''
  } catch (e) {
    memberError.value = errorMessage(e)
  }
}

async function dropMember(member) {
  memberError.value = ''
  try {
    await removeMember(event.value.id, member.id)
    members.value = members.value.filter((m) => m.id !== member.id)
  } catch (e) {
    memberError.value = errorMessage(e)
  }
}

watch(() => props.id, load, { immediate: true })
</script>

<template>
  <p v-if="loadError" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ loadError }}</p>
  <p v-else-if="!event" class="text-ink-muted">Загрузка…</p>

  <div v-else class="grid gap-6">
    <div class="flex flex-wrap items-start justify-between gap-4">
      <div class="min-w-0">
        <div class="flex flex-wrap items-center gap-2">
          <h1 class="text-2xl font-bold">{{ event.title }}</h1>
          <UiBadge :tone="STATUS_TONES[event.status]">{{ STATUS_LABELS[event.status] }}</UiBadge>
        </div>
        <p class="mt-1 text-sm text-ink-muted">{{ event.slug }}.events.skolhub.ru</p>
      </div>
      <div v-if="event.can_manage" class="flex flex-wrap gap-2">
        <UiButton
          v-for="status in event.allowed_statuses"
          :key="status"
          :variant="status === 'draft' || status === 'registration' && event.status === 'running' ? 'secondary' : 'primary'"
          @click="setStatus(status)"
        >
          {{ STATUS_ACTIONS[status] }}
        </UiButton>
        <UiButton v-if="event.status === 'draft' && !confirmDelete" variant="ghost" @click="confirmDelete = true">Удалить</UiButton>
        <span v-if="confirmDelete" class="flex items-center gap-2 text-sm">
          Удалить черновик без возможности восстановления?
          <UiButton size="sm" variant="danger" @click="remove">Удалить</UiButton>
          <UiButton size="sm" variant="ghost" @click="confirmDelete = false">Отмена</UiButton>
        </span>
      </div>
    </div>
    <p v-if="statusError" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ statusError }}</p>

    <div class="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
      <button
        v-for="item in tabs"
        :key="item.id"
        type="button"
        role="tab"
        :aria-selected="tab === item.id"
        class="-mb-px whitespace-nowrap border-b-2 px-3 py-2 text-sm"
        :class="tab === item.id ? 'border-brand-600 font-medium text-brand-700' : 'border-transparent text-ink-muted hover:text-ink'"
        @click="tab = item.id"
      >
        {{ item.label }}
      </button>
    </div>

    <form v-if="tab === 'main'" class="grid gap-6" @submit.prevent="save">
      <fieldset :disabled="readonly" class="grid gap-6">
        <UiCard>
          <template #title>Описание</template>
          <div class="grid gap-4">
            <UiInput v-model="form.title" label="Название" />
            <UiInput v-model="form.slug" label="Адрес" :hint="`${form.slug}.events.skolhub.ru`" />
            <UiInput v-model="form.short_description" label="Кратко" hint="Одна-две фразы для карточки и обложки лендинга" maxlength="300" />
            <label class="grid gap-1.5 text-sm">
              <span class="font-medium">Подробное описание</span>
              <textarea v-model="form.description" rows="6" class="rounded-control border border-line bg-surface px-3 py-2" />
            </label>
          </div>
        </UiCard>

        <UiCard>
          <template #title>Обложка</template>
          <div class="flex flex-wrap items-center gap-4">
            <img v-if="event.cover_file_id" :src="`/api/v1/public/files/${event.cover_file_id}`" alt="Обложка мероприятия" class="h-24 w-40 rounded-control object-cover" />
            <p v-else class="text-sm text-ink-muted">Картинка для лендинга и карточки мероприятия: JPEG, PNG или WebP, лучше 1600×900.</p>
            <label v-if="!readonly" class="cursor-pointer rounded-control border border-line bg-surface px-3 py-2 text-sm hover:bg-brand-50">
              {{ coverUploading ? 'Загрузка…' : event.cover_file_id ? 'Заменить' : 'Загрузить' }}
              <input type="file" accept="image/jpeg,image/png,image/webp" class="sr-only" @change="setCover($event.target.files[0]); $event.target.value = ''" />
            </label>
            <UiButton v-if="event.cover_file_id && !readonly" size="sm" variant="ghost" @click="setCover(null)">Убрать</UiButton>
          </div>
          <p v-if="coverError" role="alert" class="mt-2 text-sm text-red-700">{{ coverError }}</p>
        </UiCard>

        <UiCard>
          <template #title>Когда и где</template>
          <div class="grid gap-4 sm:grid-cols-2">
            <UiInput v-model="form.date_start" type="date" label="Начало" />
            <UiInput v-model="form.date_end" type="date" label="Окончание" />
            <UiInput v-model="form.place" label="Место" class="sm:col-span-2" placeholder="Гимназия Сколково, ул. Новая, 100" />
            <label class="grid gap-1.5 text-sm">
              <span class="font-medium">Формат</span>
              <select v-model="form.format" class="h-10 rounded-control border border-line bg-surface px-3">
                <option v-for="(label, value) in FORMAT_LABELS" :key="value" :value="value">{{ label }}</option>
              </select>
            </label>
            <label class="grid gap-1.5 text-sm">
              <span class="font-medium">Уровень</span>
              <select v-model="form.level" class="h-10 rounded-control border border-line bg-surface px-3">
                <option v-for="(label, value) in LEVEL_LABELS" :key="value" :value="value">{{ label }}</option>
              </select>
            </label>
          </div>
        </UiCard>

        <UiCard v-if="form.modules.registration">
          <template #title>Приём заявок</template>
          <div class="grid gap-4 sm:grid-cols-2">
            <UiInput v-model="form.registration_opens_at" type="datetime-local" label="Открывается" />
            <UiInput v-model="form.registration_closes_at" type="datetime-local" label="Закрывается" />
          </div>
          <p class="mt-3 text-sm text-ink-muted">Заявки принимаются, когда мероприятие в статусе «Регистрация» и время попадает в этот интервал.</p>
        </UiCard>

        <UiCard>
          <template #title>Модули</template>
          <div class="flex flex-wrap gap-x-6 gap-y-3">
            <label v-for="(label, module) in MODULE_LABELS" :key="module" class="flex items-center gap-2">
              <input v-model="form.modules[module]" type="checkbox" class="size-4 accent-brand-600" />
              {{ label }}
            </label>
          </div>
        </UiCard>
      </fieldset>

      <div v-if="!readonly" class="flex items-center gap-3">
        <UiButton type="submit" variant="primary" :loading="saving">Сохранить</UiButton>
        <span v-if="saveError" role="alert" class="text-sm text-red-700">{{ saveError }}</span>
        <span v-else-if="savedAt" class="text-sm text-ink-muted" role="status">Сохранено</span>
      </div>
    </form>

    <EventItemsEditor
      v-else-if="tab === 'directions'"
      v-model:items="event.directions"
      :event-id="event.id"
      kind="directions"
      :readonly="readonly"
      add-label="Добавить направление"
      empty-text="Направлений пока нет. Если мероприятие без направлений, оставьте список пустым."
      :fields="[{ key: 'title', label: 'Название', type: 'text' }, { key: 'description', label: 'Описание', type: 'textarea' }]"
    />

    <EventItemsEditor
      v-else-if="tab === 'stages'"
      v-model:items="event.stages"
      :event-id="event.id"
      kind="stages"
      :readonly="readonly"
      add-label="Добавить этап"
      empty-text="Этапов пока нет."
      :fields="[
        { key: 'title', label: 'Название', type: 'text' },
        { key: 'kind', label: 'Формат', type: 'select', options: { remote: 'Заочный', onsite: 'Очный' } },
        { key: 'date_start', label: 'Начало', type: 'date' },
        { key: 'date_end', label: 'Окончание', type: 'date' },
        { key: 'description', label: 'Описание', type: 'textarea' },
      ]"
    />

    <EventItemsEditor
      v-else-if="tab === 'forms'"
      v-model:items="event.participation_forms"
      :event-id="event.id"
      kind="forms"
      :readonly="readonly"
      add-label="Добавить форму участия"
      empty-text="Форм участия пока нет."
      :fields="[{ key: 'title', label: 'Название', type: 'text' }]"
    />

    <ApplicationsPanel v-else-if="tab === 'applications'" :event="event" />

    <FormBuilder v-else-if="tab === 'form'" :event-id="event.id" :readonly="readonly" />

    <EvaluationPanel v-else-if="tab === 'evaluation'" :event="event" />

    <div v-else-if="tab === 'team'" class="grid gap-4">
      <form v-if="!readonly" class="flex flex-wrap items-start gap-3" novalidate @submit.prevent="invite">
        <UiInput v-model="memberEmail" type="email" placeholder="expert@example.ru" aria-label="Email" class="min-w-0 flex-1" :error="memberError" />
        <select v-model="memberRole" aria-label="Роль" class="h-10 rounded-control border border-line bg-surface px-3">
          <option v-for="(label, value) in ROLE_LABELS" :key="value" :value="value">{{ label }}</option>
        </select>
        <UiButton type="submit" variant="primary">Добавить</UiButton>
      </form>
      <p class="text-sm text-ink-muted">Если человека ещё нет в системе, он сможет войти по ссылке, отправленной на этот адрес.</p>
      <ul class="divide-y divide-line rounded-card border border-line bg-surface">
        <li v-for="member in members" :key="member.id" class="flex flex-wrap items-center gap-3 px-4 py-3">
          <div class="min-w-0 flex-1">
            <p class="font-medium">{{ member.full_name }}</p>
            <p class="text-sm text-ink-muted">{{ member.email }}</p>
          </div>
          <UiBadge :tone="member.role === 'organizer' ? 'brand' : 'neutral'">{{ ROLE_LABELS[member.role] }}</UiBadge>
          <UiButton v-if="!readonly" size="sm" variant="ghost" @click="dropMember(member)">Убрать</UiButton>
        </li>
      </ul>
    </div>
  </div>
</template>
