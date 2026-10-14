<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { MODULE_LABELS, createEvent, fetchEventTypes, fetchEvents, isSlugAvailable, slugify } from '@/api/events'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

const router = useRouter()
const types = ref([])
const previous = ref([])
const type = ref('')
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
    ;[types.value, previous.value] = await Promise.all([fetchEventTypes(), fetchEvents()])
  } catch (e) {
    error.value = errorMessage(e)
  }
})

watch(title, (value) => {
  titleError.value = ''
  if (!slugTouched.value) slug.value = slugify(value)
})

watch(copyFrom, (id) => {
  const source = previous.value.find((event) => String(event.id) === String(id))
  if (source) type.value = source.type
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
  if (!type.value) error.value = 'Выберите тип мероприятия'
  if (titleError.value || slugError.value || error.value) return

  saving.value = true
  try {
    const event = await createEvent({
      type: type.value,
      title: title.value.trim(),
      slug: slug.value,
      copy_from_id: copyFrom.value ? Number(copyFrom.value) : null,
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

    <fieldset class="grid gap-3">
      <legend class="mb-3 font-semibold">Тип</legend>
      <label v-if="previous.length" class="grid gap-1.5 text-sm">
        <span class="font-medium">Скопировать настройки прошлого мероприятия</span>
        <select v-model="copyFrom" class="h-10 rounded-control border border-line bg-surface px-3">
          <option value="">Не копировать, начать с шаблона</option>
          <option v-for="event in previous" :key="event.id" :value="event.id">{{ event.title }}</option>
        </select>
      </label>
      <div class="grid gap-3 sm:grid-cols-2">
        <label
          v-for="item in types"
          :key="item.id"
          class="cursor-pointer rounded-card border bg-surface p-4 transition-colors has-[:checked]:border-brand-500 has-[:checked]:bg-brand-50"
          :class="{ 'pointer-events-none opacity-60': copyFrom }"
        >
          <input v-model="type" type="radio" name="type" :value="item.id" class="sr-only" />
          <span class="font-semibold">{{ item.title }}</span>
          <span class="mt-1 block text-sm text-ink-muted">{{ item.description }}</span>
          <span class="mt-3 flex flex-wrap gap-1">
            <span
              v-for="(enabled, module) in item.modules"
              v-show="enabled"
              :key="module"
              class="rounded-full bg-canvas px-2 py-0.5 text-xs text-ink-muted"
            >{{ MODULE_LABELS[module] }}</span>
          </span>
        </label>
      </div>
    </fieldset>

    <fieldset class="grid gap-4">
      <legend class="mb-3 font-semibold">Название и адрес</legend>
      <UiInput v-model="title" label="Название" placeholder="SkolStart 2027" :error="titleError" />
      <UiInput
        v-model="slug"
        label="Адрес"
        :hint="slug ? `Страница: ${slug}.events.skolhub.ru` : 'Формируется из названия, можно изменить'"
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
