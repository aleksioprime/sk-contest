<script setup>
/** Заявитель в карточке заявки: контакты, связь с человеком из базы и поиск подходящего. */
import { onMounted, ref, watch } from 'vue'
import { PERSON_KIND_LABELS, fetchMatches, linkPerson, searchPeople, unlinkPerson, updateContact } from '@/api/applications'
import { errorMessage } from '@/api/http'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

const props = defineProps({
  application: { type: Object, required: true },
  eventId: { type: Number, required: true },
})
const emit = defineEmits(['changed'])

const matches = ref([])
const query = ref('')
const found = ref([])
const searched = ref(false)
const error = ref('')
const busy = ref(false)
const editing = ref(false)
const contact = ref({})

async function loadMatches() {
  try {
    matches.value = await fetchMatches(props.application.id)
  } catch {
    matches.value = []
  }
}

/** Действие над заявкой: ответ сервера становится новым состоянием карточки. */
async function run(action) {
  busy.value = true
  error.value = ''
  try {
    emit('changed', await action())
    return true
  } catch (e) {
    error.value = errorMessage(e)
    return false
  } finally {
    busy.value = false
  }
}

async function link(person) {
  if (await run(() => linkPerson(props.application.id, person.person_id))) {
    query.value = ''
    found.value = []
  }
}

function startEdit() {
  contact.value = { ...props.application.contact }
  editing.value = true
}

async function saveContact() {
  if (await run(() => updateContact(props.application.id, contact.value))) {
    editing.value = false
    await loadMatches()
  }
}

let timer
watch(query, (value) => {
  clearTimeout(timer)
  searched.value = false
  timer = setTimeout(async () => {
    found.value = value.trim().length >= 2 ? await searchPeople(props.eventId, value).catch(() => []) : []
    searched.value = value.trim().length >= 2
  }, 300)
})

onMounted(loadMatches)
</script>

<template>
  <div class="grid gap-3 rounded-control border border-line bg-canvas p-4 text-sm">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class="font-semibold">Заявитель</p>
      <UiBadge v-if="!application.is_linked && application.source === 'import'">Из архива</UiBadge>
      <UiBadge v-else :tone="application.is_linked ? 'success' : 'warning'">{{ application.is_linked ? 'Связан с учётной записью' : 'Без учётной записи' }}</UiBadge>
    </div>

    <form v-if="editing" class="grid gap-3 sm:grid-cols-2" novalidate @submit.prevent="saveContact">
      <UiInput v-model="contact.name" label="ФИО" />
      <UiInput v-model="contact.email" type="email" label="Email" />
      <UiInput v-model="contact.phone" label="Телефон" />
      <UiInput v-model="contact.organization" label="Школа или организация" />
      <UiInput v-model="contact.grade" label="Класс" />
      <div class="flex items-end gap-2">
        <UiButton type="submit" size="sm" variant="primary" :loading="busy">Сохранить</UiButton>
        <UiButton size="sm" variant="ghost" @click="editing = false">Отмена</UiButton>
      </div>
    </form>
    <dl v-else class="grid gap-x-4 gap-y-1 sm:grid-cols-[120px_1fr]">
      <template v-if="application.is_linked">
        <dt class="text-ink-muted">Учётная запись</dt>
        <dd>{{ application.applicant_name }}, {{ application.applicant_email }}</dd>
      </template>
      <dt class="text-ink-muted">Указал в заявке</dt>
      <dd>
        {{ [application.contact.name, application.contact.email, application.contact.phone].filter(Boolean).join(', ') || '—' }}
        <button type="button" class="ml-1 text-brand-700 hover:underline" @click="startEdit">Исправить</button>
      </dd>
      <template v-if="application.contact.organization || application.contact.grade">
        <dt class="text-ink-muted">Школа, класс</dt>
        <dd>{{ [application.contact.organization, application.contact.grade].filter(Boolean).join(', ') }}</dd>
      </template>
    </dl>

    <div class="grid gap-2 border-t border-line pt-3">
      <p class="font-medium">{{ application.is_linked ? 'Передать заявку другому человеку' : 'Присоединить к человеку из базы' }}</p>
      <p v-if="!application.is_linked && application.source !== 'import'" class="text-ink-muted">Если никого не выбрать, при подтверждении человек определится по email: найдётся существующий или будет создан новый.</p>
      <ul v-if="matches.length" class="grid gap-1" aria-label="Похожие люди">
        <li v-for="person in matches" :key="person.person_id" class="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface px-3 py-2">
          <span class="min-w-0 flex-1">
            <span class="font-medium">{{ person.full_name }}</span>
            <span class="text-ink-muted"> · {{ PERSON_KIND_LABELS[person.kind] }}{{ person.class_name ? `, ${person.class_name}` : '' }}{{ person.email ? ` · ${person.email}` : '' }}</span>
          </span>
          <UiBadge v-if="person.by_email" tone="brand">совпал email</UiBadge>
          <UiButton size="sm" :loading="busy" @click="link(person)">Присоединить</UiButton>
        </li>
      </ul>
      <input v-model="query" type="search" placeholder="Поиск по ФИО или email" aria-label="Поиск человека" class="h-10 rounded-control border border-line bg-surface px-3" />
      <ul v-if="found.length" class="grid gap-1" aria-label="Результаты поиска">
        <li v-for="person in found" :key="person.person_id" class="flex flex-wrap items-center gap-2 rounded-control border border-line bg-surface px-3 py-2">
          <span class="min-w-0 flex-1">
            <span class="font-medium">{{ person.full_name }}</span>
            <span class="text-ink-muted"> · {{ PERSON_KIND_LABELS[person.kind] }}{{ person.class_name ? `, ${person.class_name}` : '' }}{{ person.email ? ` · ${person.email}` : '' }}</span>
          </span>
          <UiButton size="sm" :loading="busy" @click="link(person)">Присоединить</UiButton>
        </li>
      </ul>
      <p v-else-if="searched" class="text-ink-muted">Никого не нашли.</p>
      <div v-if="application.is_linked && application.status === 'requested'">
        <UiButton size="sm" variant="ghost" :loading="busy" @click="run(() => unlinkPerson(application.id))">Снять связь</UiButton>
      </div>
    </div>
    <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
  </div>
</template>
