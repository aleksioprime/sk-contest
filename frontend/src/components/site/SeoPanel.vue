<script setup>
import ImageField from './ImageField.vue'

const props = defineProps({
  seo: { type: Object, required: true },
  eventTitle: { type: String, default: '' },
})
const emit = defineEmits(['change'])
const set = (field, value) => emit('change', { ...props.seo, [field]: value })
</script>

<template>
  <div class="grid gap-4 text-sm">
    <p class="text-ink-muted">Как сайт выглядит в поиске и при отправке ссылки в мессенджер.</p>
    <label class="grid gap-1.5">
      <span class="font-medium">Заголовок страницы</span>
      <input :value="seo.title" maxlength="120" :placeholder="eventTitle" class="h-9 rounded-control border border-line bg-surface px-3" @change="set('title', $event.target.value)" />
    </label>
    <label class="grid gap-1.5">
      <span class="font-medium">Описание</span>
      <textarea :value="seo.description" maxlength="300" rows="3" class="rounded-control border border-line bg-surface px-3 py-2" @change="set('description', $event.target.value)" />
      <span class="text-xs text-ink-muted">До 300 символов. Если пусто — краткое описание мероприятия.</span>
    </label>
    <ImageField :model-value="seo.image" label="Картинка для ссылки (1200×630)" ratio="1.91:1" @update:model-value="set('image', $event)" />
    <label class="grid gap-1.5">
      <span class="font-medium">Номер счётчика Яндекс.Метрики</span>
      <input
        :value="seo.metrika"
        inputmode="numeric"
        maxlength="12"
        placeholder="Например, 98765432"
        class="h-9 rounded-control border border-line bg-surface px-3"
        @change="set('metrika', $event.target.value.replace(/\D/g, ''))"
      />
    </label>
  </div>
</template>
