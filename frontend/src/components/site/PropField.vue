<script setup>
/** Поле настройки блока, построенное по схеме из @sk-events/blocks. */
import FileField from './FileField.vue'
import ImageField from './ImageField.vue'
import ListField from './ListField.vue'
import RichTextEditor from './RichTextEditor.vue'

defineProps({
  prop: { type: Object, required: true },
  error: { type: String, default: '' },
})
const value = defineModel({ type: [String, Boolean, Object, Array], default: null })
</script>

<template>
  <div class="grid gap-1">
    <RichTextEditor v-if="prop.type === 'richtext'" v-model="value" :label="prop.label" />
    <ImageField v-else-if="prop.type === 'image'" v-model="value" :label="prop.label" :ratio="prop.ratio ?? '16:9'" />
    <FileField v-else-if="prop.type === 'file'" v-model="value" :label="prop.label" />
    <ListField v-else-if="prop.type === 'list'" v-model="value" :prop="prop" />
    <label v-else-if="prop.type === 'bool'" class="flex items-center gap-2 text-sm">
      <input v-model="value" type="checkbox" class="size-4 accent-brand-600" />
      {{ prop.label }}
    </label>
    <label v-else-if="prop.type === 'select'" class="grid gap-1.5 text-sm">
      <span class="font-medium">{{ prop.label }}</span>
      <select v-model="value" class="h-9 rounded-control border border-line bg-surface px-2">
        <option v-for="option in prop.options" :key="option" :value="option">{{ prop.labels?.[option] ?? option }}</option>
      </select>
    </label>
    <label v-else class="grid gap-1.5 text-sm">
      <span class="font-medium">{{ prop.label }}</span>
      <textarea
        v-if="prop.multiline"
        v-model="value"
        rows="3"
        :maxlength="prop.max"
        :placeholder="prop.placeholder"
        class="rounded-control border border-line bg-surface px-3 py-2"
      />
      <input
        v-else
        v-model="value"
        :type="prop.type === 'url' ? 'url' : 'text'"
        :maxlength="prop.max"
        :placeholder="prop.placeholder ?? (prop.type === 'url' ? 'https://' : '')"
        class="h-9 rounded-control border border-line bg-surface px-3"
      />
    </label>
    <p v-if="error" class="text-sm text-red-700">{{ error }}</p>
  </div>
</template>
