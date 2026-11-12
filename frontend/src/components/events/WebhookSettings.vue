<script setup>
/** Вебхук для внешних форм: адрес и соответствие полей. Поля сохраняются вместе с анкетой, адрес — сразу. */
import { computed, onMounted, ref } from 'vue'
import { ASKABLE_FIELDS, disableWebhook, enableWebhook, fetchWebhook } from '@/api/applications'
import { errorMessage, UiButton, UiCard, UiConfirm, UiCopyField } from 'sk-ui'

const props = defineProps({
  eventId: { type: Number, required: true },
  fields: { type: Array, default: () => [] },
})
const names = defineModel({ type: Object, required: true })

const url = ref(null)
const error = ref('')
const busy = ref(false)
const confirmChange = ref(false)

// Какие поля можно сопоставить: встроенные и вопросы анкеты, кроме файлов
const targets = computed(() => [
  { key: 'full_name', label: 'ФИО' },
  { key: 'email', label: 'Email' },
  ...Object.entries(ASKABLE_FIELDS).map(([key, label]) => ({ key, label })),
  ...props.fields.filter((f) => f.type !== 'file').map((f) => ({ key: f.key, label: f.label })),
])

function setName(key, value) {
  const next = { ...names.value }
  if (value.trim()) next[key] = value.trim()
  else delete next[key]
  names.value = next
}

async function run(action) {
  busy.value = true
  error.value = ''
  confirmChange.value = false
  try {
    url.value = await action()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}

onMounted(() => run(() => fetchWebhook(props.eventId)))
</script>

<template>
  <UiCard>
    <template #title>Вебхук для внешних форм</template>
    <div class="grid grid-cols-[minmax(0,1fr)] gap-4 text-sm">
      <p class="text-ink-muted">
        Заявки из других сервисов, например Tilda, сразу попадают к модератору. В настройках формы Tilda выберите
        «Webhook» и вставьте этот адрес. Подойдёт любое приложение, которое отправляет POST в формате JSON или формы.
      </p>
      <template v-if="url">
        <UiCopyField :value="url" label="Адрес вебхука" />
        <div class="flex flex-wrap items-center gap-2">
          <UiButton size="sm" variant="ghost" @click="confirmChange = true">Сменить адрес</UiButton>
          <UiConfirm v-model:open="confirmChange" title="Сменить адрес вебхука?" confirm-label="Сменить" variant="danger" @confirm="run(() => enableWebhook(eventId))">
            Прежний адрес перестанет работать, внешние формы нужно будет настроить заново.
          </UiConfirm>
          <UiButton size="sm" variant="ghost" :loading="busy" @click="run(async () => (await disableWebhook(eventId), null))">Выключить</UiButton>
        </div>

        <details>
          <summary class="cursor-pointer font-medium">Соответствие полей</summary>
          <p class="mt-2 text-ink-muted">
            Обычно настраивать не нужно: распространённые названия (Name, Email, Phone, Имя, Телефон, Школа) и подписи вопросов
            распознаются сами. Если поле называется иначе, укажите его имя во внешней форме.
          </p>
          <div class="mt-3 grid gap-2 sm:grid-cols-2">
            <label v-for="target in targets" :key="target.key" class="grid gap-1">
              <span class="text-ink-muted">{{ target.label }}</span>
              <input :value="names[target.key] ?? ''" placeholder="определяется автоматически" class="h-9 rounded-control border border-line bg-surface px-3" @change="setName(target.key, $event.target.value)" />
            </label>
          </div>
        </details>
      </template>
      <div v-else><UiButton size="sm" :loading="busy" @click="run(() => enableWebhook(eventId))">Включить вебхук</UiButton></div>
      <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
    </div>
  </UiCard>
</template>
