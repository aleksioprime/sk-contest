<script setup>
import { FONT_PAIRS, RADII, THEME_PRESETS } from '@sk-events/blocks'
import ImageField from './ImageField.vue'

const props = defineProps({ theme: { type: Object, required: true } })
const emit = defineEmits(['change'])

function preset(key) {
  const p = THEME_PRESETS[key]
  emit('change', { ...props.theme, preset: key, accent: p.accent, fontPair: p.fontPair, radius: p.radius })
}
const set = (field, value) => emit('change', { ...props.theme, [field]: value })
</script>

<template>
  <div class="grid gap-5 text-sm">
    <div class="grid gap-2">
      <span class="font-medium">Готовая тема</span>
      <div class="grid grid-cols-2 gap-2">
        <button
          v-for="(p, key) in THEME_PRESETS"
          :key="key"
          type="button"
          class="flex items-center gap-2 rounded-control border px-3 py-2 text-left"
          :class="theme.preset === key ? 'border-brand-500 bg-brand-50' : 'border-line hover:bg-brand-50'"
          @click="preset(key)"
        >
          <span class="size-5 shrink-0 rounded-full" :style="{ background: p.accent }" />
          {{ p.title }}
        </button>
      </div>
    </div>
    <label class="flex items-center justify-between gap-3">
      <span class="font-medium">Основной цвет</span>
      <span class="flex items-center gap-2">
        <input type="color" :value="theme.accent" class="h-9 w-12 cursor-pointer rounded border border-line" aria-label="Основной цвет" @input="set('accent', $event.target.value)" />
        <code class="text-ink-muted">{{ theme.accent }}</code>
      </span>
    </label>
    <label class="grid gap-1.5">
      <span class="font-medium">Шрифты</span>
      <select :value="theme.fontPair" class="h-9 rounded-control border border-line bg-surface px-2" @change="set('fontPair', $event.target.value)">
        <option v-for="(pair, key) in FONT_PAIRS" :key="key" :value="key">{{ pair.title }}</option>
      </select>
    </label>
    <div class="grid gap-1.5">
      <span class="font-medium">Скругления</span>
      <div class="flex gap-1.5" role="radiogroup" aria-label="Скругления">
        <button
          v-for="(radius, key) in RADII"
          :key="key"
          type="button"
          role="radio"
          :aria-checked="theme.radius === key"
          class="flex-1 border px-3 py-1.5"
          :style="{ borderRadius: radius[1] }"
          :class="theme.radius === key ? 'border-brand-500 bg-brand-100 text-brand-700' : 'border-line hover:bg-brand-50'"
          @click="set('radius', key)"
        >
          {{ radius[0] }}
        </button>
      </div>
    </div>
    <div class="grid gap-1.5">
      <span class="font-medium">Оформление</span>
      <div class="flex gap-1.5" role="radiogroup" aria-label="Светлая или тёмная">
        <button
          v-for="(label, key) in { light: 'Светлое', dark: 'Тёмное' }"
          :key="key"
          type="button"
          role="radio"
          :aria-checked="theme.mode === key"
          class="flex-1 rounded-control border px-3 py-1.5"
          :class="theme.mode === key ? 'border-brand-500 bg-brand-100 text-brand-700' : 'border-line hover:bg-brand-50'"
          @click="set('mode', key)"
        >
          {{ label }}
        </button>
      </div>
    </div>
    <ImageField :model-value="theme.logo" label="Логотип (для шапки)" ratio="free" @update:model-value="set('logo', $event)" />
    <ImageField :model-value="theme.favicon" label="Значок во вкладке браузера (квадрат)" ratio="1:1" @update:model-value="set('favicon', $event)" />
  </div>
</template>
