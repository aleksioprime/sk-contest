<script setup>
/** Конструктор анкеты заявки: поля, команда, ограничения и согласия. */
import { computed, onMounted, ref } from 'vue'
import { fetchForm, resetForm, saveForm } from '@/api/applications'
import { slugify } from '@/api/events'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'

const props = defineProps({
  eventId: { type: Number, required: true },
  readonly: { type: Boolean, default: false },
})

const FIELD_TYPES = {
  text: 'Строка',
  textarea: 'Текст',
  select: 'Выбор одного',
  multiselect: 'Выбор нескольких',
  checkbox: 'Отметка',
  number: 'Число',
  date: 'Дата',
  email: 'Email',
  phone: 'Телефон',
  url: 'Ссылка',
  file: 'Файл',
}

const form = ref(null)
const error = ref('')
const notice = ref('')
const saving = ref(false)
const confirmReset = ref(false)
const gradesText = ref('')

const conditionSources = computed(() => form.value.fields.filter((f) => ['select', 'checkbox'].includes(f.type)))

function keyFor(label, except) {
  const base = (slugify(label).replace(/-/g, '_') || 'field').replace(/^[^a-z]+/, '') || 'field'
  let key = base.slice(0, 36)
  let n = 2
  while (form.value.fields.some((f) => f !== except && f.key === key)) key = `${base.slice(0, 34)}_${n++}`
  return key
}

function addField() {
  const field = { key: '', type: 'text', label: 'Новый вопрос', help: '', required: false, options: [], visible_if: null }
  field.key = keyFor(field.label, field)
  form.value.fields.push(field)
}

function move(list, index, delta) {
  const [item] = list.splice(index, 1)
  list.splice(index + delta, 0, item)
}

function setOptions(field, text) {
  field.options = text.split('\n').map((s) => s.trim()).filter(Boolean)
}

function setCondition(field, source) {
  field.visible_if = source ? { field: source, equals: conditionSources.value.find((f) => f.key === source)?.type === 'checkbox' ? true : '' } : null
}

function addConsent() {
  form.value.consents.push({ key: `consent_${form.value.consents.length + 1}`, title: '', text: '', version: '1', required: true })
}

async function load() {
  error.value = ''
  try {
    form.value = await fetchForm(props.eventId)
    gradesText.value = (form.value.limits.grades ?? []).join(', ')
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function save() {
  saving.value = true
  error.value = ''
  notice.value = ''
  const grades = gradesText.value.split(/[,\s]+/).map(Number).filter((n) => n > 0)
  form.value.limits.grades = grades.length ? grades : null
  try {
    form.value = await saveForm(props.eventId, form.value)
    notice.value = 'Анкета сохранена'
  } catch (e) {
    const detail = e?.response?.data?.detail
    error.value = Array.isArray(detail) ? detail.map((d) => d.msg.replace(/^Value error, /, '')).join('. ') : errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function reset() {
  confirmReset.value = false
  try {
    form.value = await resetForm(props.eventId)
    notice.value = 'Анкета заменена анкетой по умолчанию'
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(load)
</script>

<template>
  <p v-if="!form && error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
  <SkeletonPage v-else-if="!form" :cards="2" />

  <form v-else class="grid gap-6" @submit.prevent="save">
    <fieldset :disabled="readonly" class="grid gap-6">
      <p class="text-sm text-ink-muted">Название работы, направление и форма участия есть в каждой заявке. Здесь — дополнительные вопросы.</p>

      <UiCard>
        <template #title>Вопросы</template>
        <ol class="grid gap-3">
          <li v-for="(field, index) in form.fields" :key="index" class="grid gap-3 rounded-control border border-line p-4">
            <div class="grid gap-3 sm:grid-cols-[2fr_1fr]">
              <label class="grid gap-1 text-sm">
                <span class="font-medium">Вопрос</span>
                <input v-model="field.label" class="h-10 rounded-control border border-line bg-surface px-3" @change="field.key = keyFor(field.label, field)" />
              </label>
              <label class="grid gap-1 text-sm">
                <span class="font-medium">Тип ответа</span>
                <select v-model="field.type" class="h-10 rounded-control border border-line bg-surface px-3">
                  <option v-for="(label, value) in FIELD_TYPES" :key="value" :value="value">{{ label }}</option>
                </select>
              </label>
            </div>
            <label v-if="['select', 'multiselect'].includes(field.type)" class="grid gap-1 text-sm">
              <span class="font-medium">Варианты, по одному в строке</span>
              <textarea :value="field.options.join('\n')" rows="3" class="rounded-control border border-line bg-surface px-3 py-2" @change="setOptions(field, $event.target.value)" />
            </label>
            <label class="grid gap-1 text-sm">
              <span class="font-medium">Подсказка</span>
              <input v-model="field.help" class="h-10 rounded-control border border-line bg-surface px-3" />
            </label>
            <div class="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <label class="flex items-center gap-2"><input v-model="field.required" type="checkbox" class="size-4 accent-brand-600" /> Обязательный</label>
              <label class="flex items-center gap-2">
                Показывать, если
                <select :value="field.visible_if?.field ?? ''" class="h-8 rounded-control border border-line bg-surface px-2" @change="setCondition(field, $event.target.value)">
                  <option value="">всегда</option>
                  <option v-for="source in conditionSources.filter((s) => s !== field)" :key="source.key" :value="source.key">{{ source.label }}</option>
                </select>
              </label>
              <template v-if="field.visible_if">
                <select
                  v-if="conditionSources.find((s) => s.key === field.visible_if.field)?.type === 'select'"
                  v-model="field.visible_if.equals"
                  aria-label="Значение условия"
                  class="h-8 rounded-control border border-line bg-surface px-2"
                >
                  <option v-for="option in conditionSources.find((s) => s.key === field.visible_if.field).options" :key="option" :value="option">= {{ option }}</option>
                </select>
                <span v-else class="text-ink-muted">отмечено</span>
              </template>
              <span class="ml-auto flex gap-1">
                <UiButton size="sm" variant="ghost" :disabled="index === 0" aria-label="Выше" @click="move(form.fields, index, -1)">↑</UiButton>
                <UiButton size="sm" variant="ghost" :disabled="index === form.fields.length - 1" aria-label="Ниже" @click="move(form.fields, index, 1)">↓</UiButton>
                <UiButton size="sm" variant="ghost" @click="form.fields.splice(index, 1)">Удалить</UiButton>
              </span>
            </div>
          </li>
        </ol>
        <UiButton v-if="!readonly" class="mt-3" size="sm" @click="addField">Добавить вопрос</UiButton>
      </UiCard>

      <UiCard>
        <template #title>Команда и ограничения</template>
        <div class="grid gap-4 sm:grid-cols-2">
          <label class="flex items-center gap-2 sm:col-span-2"><input v-model="form.team.enabled" type="checkbox" class="size-4 accent-brand-600" /> Командное участие</label>
          <label v-if="form.team.enabled" class="grid gap-1 text-sm"><span class="font-medium">Участников не меньше</span><input v-model.number="form.team.min" type="number" min="1" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label v-if="form.team.enabled" class="grid gap-1 text-sm"><span class="font-medium">Участников не больше</span><input v-model.number="form.team.max" type="number" min="1" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1 text-sm"><span class="font-medium">Руководителей не больше</span><input v-model.number="form.team.supervisors_max" type="number" min="0" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="flex items-center gap-2 self-end pb-2"><input v-model="form.team.require_supervisor" type="checkbox" class="size-4 accent-brand-600" /> Руководитель обязателен</label>
          <label class="grid gap-1 text-sm"><span class="font-medium">Заявок на руководителя</span><input v-model.number="form.limits.per_supervisor" type="number" min="1" placeholder="без ограничений" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1 text-sm"><span class="font-medium">Заявок на направление</span><input v-model.number="form.limits.per_direction" type="number" min="1" placeholder="без ограничений" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
          <label class="grid gap-1 text-sm sm:col-span-2"><span class="font-medium">Допустимые классы</span><input v-model="gradesText" placeholder="Например: 8, 9, 10, 11. Пусто — без ограничений" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
        </div>
      </UiCard>

      <UiCard>
        <template #title>Согласия</template>
        <div class="grid gap-3">
          <div v-for="(consent, index) in form.consents" :key="index" class="grid gap-3 rounded-control border border-line p-4">
            <div class="grid gap-3 sm:grid-cols-[3fr_1fr]">
              <label class="grid gap-1 text-sm"><span class="font-medium">Название</span><input v-model="consent.title" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
              <label class="grid gap-1 text-sm"><span class="font-medium">Версия</span><input v-model="consent.version" class="h-10 rounded-control border border-line bg-surface px-3" /></label>
            </div>
            <label class="grid gap-1 text-sm"><span class="font-medium">Текст</span><textarea v-model="consent.text" rows="4" class="rounded-control border border-line bg-surface px-3 py-2" /></label>
            <p class="text-xs text-ink-muted">Изменили текст — увеличьте версию: участникам придётся дать согласие заново.</p>
            <div class="flex items-center gap-4 text-sm">
              <label class="flex items-center gap-2"><input v-model="consent.required" type="checkbox" class="size-4 accent-brand-600" /> Обязательное</label>
              <UiButton class="ml-auto" size="sm" variant="ghost" @click="form.consents.splice(index, 1)">Удалить</UiButton>
            </div>
          </div>
          <div v-if="!readonly"><UiButton size="sm" @click="addConsent">Добавить согласие</UiButton></div>
        </div>
      </UiCard>
    </fieldset>

    <div v-if="!readonly" class="flex flex-wrap items-center gap-3">
      <UiButton type="submit" variant="primary" :loading="saving">Сохранить анкету</UiButton>
      <UiButton v-if="!confirmReset" variant="ghost" @click="confirmReset = true">Вернуть анкету по умолчанию</UiButton>
      <span v-else class="flex items-center gap-2 text-sm">
        Заменить текущие вопросы стандартными?
        <UiButton size="sm" variant="danger" @click="reset">Заменить</UiButton>
        <UiButton size="sm" variant="ghost" @click="confirmReset = false">Отмена</UiButton>
      </span>
      <span v-if="error" role="alert" class="text-sm text-red-700">{{ error }}</span>
      <span v-else-if="notice" role="status" class="text-sm text-ink-muted">{{ notice }}</span>
    </div>
  </form>
</template>
