<script setup>
import { BACKGROUNDS, VISIBILITY, getBlock } from '@sk-events/blocks'
import { computed } from 'vue'
import PropField from './PropField.vue'

const props = defineProps({
  block: { type: Object, required: true },
  errors: { type: Array, default: () => [] },
})
const emit = defineEmits(['prop', 'variant', 'common', 'close'])

const schema = computed(() => getBlock(props.block.type))
const errorOf = (name) => props.errors.find((e) => e.field === name || e.field.startsWith(`${name}.`))?.message ?? ''
const general = computed(() => props.errors.filter((e) => !e.field))
</script>

<template>
  <div class="grid gap-5">
    <div class="flex items-start justify-between gap-2">
      <div>
        <p class="font-semibold">{{ schema.title }}</p>
        <p class="text-sm text-ink-muted">{{ schema.description }}</p>
      </div>
      <button type="button" class="rounded px-2 text-ink-muted hover:bg-brand-50" aria-label="Закрыть настройки блока" @click="emit('close')">×</button>
    </div>
    <p v-for="e in general" :key="e.message" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ e.message }}</p>

    <div v-if="schema.variants.length > 1" class="grid gap-1.5 text-sm">
      <span class="font-medium">Вид</span>
      <div class="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Вид блока">
        <button
          v-for="variant in schema.variants"
          :key="variant"
          type="button"
          role="radio"
          :aria-checked="block.variant === variant"
          class="rounded-full border px-3 py-1"
          :class="block.variant === variant ? 'border-brand-500 bg-brand-100 text-brand-700' : 'border-line hover:bg-brand-50'"
          @click="emit('variant', variant)"
        >
          {{ schema.variantLabels[variant] ?? variant }}
        </button>
      </div>
    </div>

    <PropField
      v-for="(prop, name) in schema.props"
      :key="`${block.id}-${name}`"
      :prop="prop"
      :model-value="block.props[name]"
      :error="errorOf(name)"
      @update:model-value="emit('prop', name, $event)"
    />

    <details class="rounded-control border border-line p-3 text-sm">
      <summary class="font-medium">Раздел, фон и показ</summary>
      <div class="mt-3 grid gap-3">
        <label class="grid gap-1.5">
          <span>Якорь для ссылок <span class="text-ink-muted">(латиница, например program)</span></span>
          <input
            :value="block.common.anchor"
            pattern="[a-z0-9][a-z0-9-]*"
            class="h-9 rounded-control border border-line bg-surface px-3"
            @change="emit('common', 'anchor', $event.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))"
          />
        </label>
        <label class="grid gap-1.5">
          <span>Пункт меню в шапке <span class="text-ink-muted">(пусто — не показывать)</span></span>
          <input :value="block.common.menuTitle" maxlength="40" class="h-9 rounded-control border border-line bg-surface px-3" @change="emit('common', 'menuTitle', $event.target.value)" />
        </label>
        <label class="grid gap-1.5">
          <span>Фон</span>
          <select :value="block.common.background" class="h-9 rounded-control border border-line bg-surface px-2" @change="emit('common', 'background', $event.target.value)">
            <option v-for="(label, value) in BACKGROUNDS" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
        <label class="grid gap-1.5">
          <span>Когда показывать</span>
          <select :value="block.common.visibility" class="h-9 rounded-control border border-line bg-surface px-2" @change="emit('common', 'visibility', $event.target.value)">
            <option v-for="(label, value) in VISIBILITY" :key="value" :value="value">{{ label }}</option>
          </select>
        </label>
      </div>
    </details>
  </div>
</template>
