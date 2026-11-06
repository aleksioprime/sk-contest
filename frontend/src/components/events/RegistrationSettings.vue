<script setup>
/** Настройки первого шага: открытая форма и что в ней спрашивать. Сохраняются вместе с анкетой. */
import { ASKABLE_FIELDS } from '@/api/applications'
import { applyUrl } from '@/api/events'
import { UiCard, UiCopyField } from 'sk-ui'

defineProps({ slug: { type: String, required: true } })
const settings = defineModel({ type: Object, required: true })

function toggleAsked(name, checked) {
  const asked = settings.value.asked.filter((item) => item !== name)
  settings.value.asked = checked ? [...asked, name] : asked
}
</script>

<template>
  <UiCard>
    <template #title>Общая заявка</template>
    <div class="grid gap-4 text-sm">
      <p class="text-ink-muted">
        Сначала человек оставляет общую заявку, модератор её подтверждает. Приглашение в кабинет приходит на почту,
        там заполняется остальная анкета.
      </p>
      <UiCopyField :value="applyUrl(slug)" label="Адрес открытой формы" />

      <label class="flex items-start gap-2">
        <input v-model="settings.open_form" type="checkbox" class="mt-0.5 size-4 accent-brand-600" />
        <span>
          <span class="font-medium">Открытая форма</span>
          <span class="block text-ink-muted">Заявку можно оставить без входа. Если выключить, форма будет доступна только вошедшим.</span>
        </span>
      </label>
      <label class="flex items-start gap-2">
        <input v-model="settings.details_step" type="checkbox" class="mt-0.5 size-4 accent-brand-600" />
        <span>
          <span class="font-medium">Заполнение анкеты после подтверждения</span>
          <span class="block text-ink-muted">Если выключить, подтверждённая заявка сразу считается принятой: подходит для слушателей открытых событий.</span>
        </span>
      </label>

      <fieldset class="grid gap-2">
        <legend class="mb-1 font-medium">Что спрашивать, кроме ФИО и email</legend>
        <div class="flex flex-wrap gap-x-6 gap-y-2">
          <label v-for="(label, name) in ASKABLE_FIELDS" :key="name" class="flex items-center gap-2">
            <input type="checkbox" class="size-4 accent-brand-600" :checked="settings.asked.includes(name)" @change="toggleAsked(name, $event.target.checked)" />
            {{ label }}
          </label>
        </div>
        <p class="text-ink-muted">Свои вопросы добавляются ниже, отметкой «В общей заявке».</p>
      </fieldset>

      <label class="grid gap-1">
        <span class="font-medium">Текст над формой</span>
        <textarea v-model="settings.intro" rows="3" class="rounded-control border border-line bg-surface px-3 py-2" />
      </label>
      <label class="grid gap-1">
        <span class="font-medium">Текст после отправки</span>
        <textarea v-model="settings.success_text" rows="2" placeholder="Заявка получена. Когда организаторы её подтвердят, на почту придёт приглашение в личный кабинет." class="rounded-control border border-line bg-surface px-3 py-2" />
      </label>
    </div>
  </UiCard>
</template>
