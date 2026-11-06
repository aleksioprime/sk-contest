<script setup>
/** Создание мероприятия: копирование прошлого, разделы, название и адрес. */
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { MODULE_HINTS, MODULE_LABELS, applyUrl, createEvent, fetchEvent, fetchEvents, isSlugAvailable, slugify } from '@/api/events'
import { errorMessage, UiButton, UiInput, UiSelect } from 'sk-ui'

const router = useRouter()
const previous = ref([])
const modules = ref(Object.fromEntries(Object.keys(MODULE_LABELS).map((module) => [module, true])))
const copyFrom = ref('')
const title = ref('')
const slug = ref('')
const slugTouched = ref(false)
const slugError = ref('')
const titleError = ref('')
const error = ref('')
const saving = ref(false)

onMounted(async () => {
  try {
    previous.value = await fetchEvents('all')
  } catch (e) {
    error.value = errorMessage(e)
  }
})

watch(title, (value) => {
  titleError.value = ''
  if (!slugTouched.value) slug.value = slugify(value)
})

watch(copyFrom, async (id) => {
  if (!id) return
  try {
    modules.value = { ...modules.value, ...(await fetchEvent(id)).modules }
  } catch (e) {
    error.value = errorMessage(e)
  }
})

let slugTimer
watch(slug, (value) => {
  slugError.value = ''
  clearTimeout(slugTimer)
  if (!value) return
  if (!/^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/.test(value)) {
    slugError.value = 'Только латинские буквы, цифры и дефис; без дефиса в начале и конце'
    return
  }
  slugTimer = setTimeout(async () => {
    if (!(await isSlugAvailable(value))) slugError.value = 'Этот адрес уже занят'
  }, 300)
})

async function submit() {
  error.value = ''
  if (title.value.trim().length < 3) titleError.value = 'Название — не меньше 3 символов'
  if (!slug.value) slugError.value = 'Укажите адрес'
  if (titleError.value || slugError.value || error.value) return

  saving.value = true
  try {
    const event = await createEvent({
      title: title.value.trim(),
      slug: slug.value,
      copy_from_id: copyFrom.value ? Number(copyFrom.value) : null,
      modules: modules.value,
    })
    await router.push({ name: 'event', params: { id: event.id } })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <form class="grid max-w-3xl gap-8" novalidate @submit.prevent="submit">
    <h1 class="text-2xl font-bold">Новое мероприятие</h1>

    <label v-if="previous.length" class="grid gap-1.5 text-sm">
      <span class="font-medium">Скопировать настройки прошлого мероприятия</span>
      <UiSelect v-model="copyFrom">
        <option value="">Не копировать</option>
        <option v-for="event in previous" :key="event.id" :value="event.id">{{ event.title }}</option>
      </UiSelect>
    </label>

    <fieldset class="grid gap-3">
      <legend class="mb-3 font-semibold">Разделы</legend>
      <div class="grid gap-3 sm:grid-cols-2">
        <label
          v-for="(label, module) in MODULE_LABELS"
          :key="module"
          class="flex cursor-pointer items-start gap-3 rounded-card border border-line bg-surface p-4 transition-colors has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50"
        >
          <input v-model="modules[module]" type="checkbox" class="mt-0.5" />
          <span>
            <span class="font-semibold">{{ label }}</span>
            <span class="mt-1 block text-sm text-ink-muted">{{ MODULE_HINTS[module] }}</span>
          </span>
        </label>
      </div>
      <p class="text-sm text-ink-muted">Разделы можно изменить позже в настройках мероприятия.</p>
    </fieldset>

    <fieldset class="grid gap-4">
      <legend class="mb-3 font-semibold">Название и адрес</legend>
      <UiInput v-model="title" label="Название" placeholder="SkolStart 2027" :error="titleError" />
      <UiInput
        v-model="slug"
        label="Адрес"
        :hint="slug ? `Открытая форма заявки: ${applyUrl(slug)}` : 'Формируется из названия, можно изменить'"
        :error="slugError"
        @input="slugTouched = true"
      />
    </fieldset>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>

    <div class="flex gap-3">
      <UiButton type="submit" variant="primary" :loading="saving">Создать черновик</UiButton>
      <UiButton variant="ghost" @click="router.back()">Отмена</UiButton>
    </div>
  </form>
</template>
