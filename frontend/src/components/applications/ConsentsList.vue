<script setup>
/** Список согласий с текстом и ошибками. Общий для открытой формы и анкеты в кабинете. */
defineProps({
  consents: { type: Array, required: true },
  errors: { type: Object, default: () => ({}) },
})
const accepted = defineModel({ type: Array, default: () => [] })
</script>

<template>
  <div class="grid gap-4">
    <div v-for="consent in consents" :key="consent.key">
      <label class="flex items-start gap-2">
        <input v-model="accepted" type="checkbox" :value="consent.key" class="mt-1 size-4 accent-brand-600" />
        <span class="font-medium">{{ consent.title }}<span v-if="consent.required" class="text-red-600" aria-hidden="true"> *</span></span>
      </label>
      <details class="ml-6 mt-1 text-sm text-ink-muted">
        <summary class="cursor-pointer">Текст согласия</summary>
        <p class="mt-1 whitespace-pre-line">{{ consent.text }}</p>
      </details>
      <p v-if="errors[`consent:${consent.key}`]" class="ml-6 text-sm text-red-600">{{ errors[`consent:${consent.key}`] }}</p>
    </div>
  </div>
</template>
