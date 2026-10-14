<script setup>
import { computed, useAttrs, useId } from 'vue'

defineOptions({ inheritAttrs: false })

defineProps({
  label: { type: String, default: '' },
  hint: { type: String, default: '' },
  error: { type: String, default: '' },
})
const model = defineModel({ type: [String, Number], default: '' })
const id = useId()
const attrs = useAttrs()
const inputAttrs = computed(() => Object.fromEntries(Object.entries(attrs).filter(([key]) => key !== 'class')))
</script>

<template>
  <div class="grid gap-1.5" :class="attrs.class">
    <label v-if="label" :for="id" class="text-sm font-medium">{{ label }}</label>
    <input
      :id="id"
      v-model="model"
      v-bind="inputAttrs"
      :aria-invalid="!!error || undefined"
      :aria-describedby="error || hint ? `${id}-help` : undefined"
      class="h-10 rounded-control border bg-surface px-3 outline-none transition-colors focus:border-brand-500"
      :class="error ? 'border-red-500' : 'border-line'"
    />
    <p v-if="error || hint" :id="`${id}-help`" class="text-sm" :class="error ? 'text-red-600' : 'text-ink-muted'">
      {{ error || hint }}
    </p>
  </div>
</template>
