<script setup>
import { ref } from 'vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  pages: { type: Array, required: true },
  current: { type: Number, required: true },
})
const emit = defineEmits(['select', 'add', 'update', 'remove'])
const title = ref('')

function add() {
  const name = title.value.trim()
  if (!name) return
  emit('add', name)
  title.value = ''
}
</script>

<template>
  <div class="grid gap-4 text-sm">
    <p class="text-ink-muted">Главная страница открывается по адресу сайта, остальные — по адресу сайта и имени страницы.</p>
    <ul class="grid gap-2">
      <li v-for="(page, index) in pages" :key="index" class="grid gap-2 rounded-control border p-3" :class="index === current ? 'border-brand-500' : 'border-line'">
        <div class="flex items-center gap-2">
          <input
            :value="page.title"
            maxlength="80"
            aria-label="Название страницы"
            class="h-8 min-w-0 flex-1 rounded-control border border-line bg-surface px-2"
            @change="emit('update', index, { title: $event.target.value })"
          />
          <UiButton v-if="index !== current" size="sm" variant="ghost" @click="emit('select', index)">Открыть</UiButton>
          <UiButton v-if="index > 0" size="sm" variant="ghost" @click="emit('remove', index)">Удалить</UiButton>
        </div>
        <label v-if="index > 0" class="flex items-center gap-1 text-ink-muted">
          /
          <input
            :value="page.path"
            aria-label="Адрес страницы"
            class="h-8 min-w-0 flex-1 rounded-control border border-line bg-surface px-2 text-ink"
            @change="emit('update', index, { path: $event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, '') })"
          />
        </label>
        <span v-else class="text-ink-muted">Главная</span>
      </li>
    </ul>
    <form v-if="props.pages.length < 10" class="flex gap-2" @submit.prevent="add">
      <input v-model="title" placeholder="Название новой страницы" class="h-9 min-w-0 flex-1 rounded-control border border-line bg-surface px-3" />
      <UiButton type="submit" size="sm">Добавить</UiButton>
    </form>
  </div>
</template>
