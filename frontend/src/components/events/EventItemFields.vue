<script setup>
defineProps({ fields: { type: Array, required: true } })
const draft = defineModel('draft', { type: Object, required: true })
</script>

<template>
  <label v-for="field in fields" :key="field.key" class="grid gap-1 text-sm">
    <span class="font-medium">{{ field.label }}</span>
    <textarea v-if="field.type === 'textarea'" v-model="draft[field.key]" rows="3" class="rounded-control border border-line bg-surface px-3 py-2" />
    <select v-else-if="field.type === 'select'" v-model="draft[field.key]" class="h-10 rounded-control border border-line bg-surface px-3">
      <option v-for="(label, value) in field.options" :key="value" :value="value">{{ label }}</option>
    </select>
    <input v-else v-model="draft[field.key]" :type="field.type" class="h-10 rounded-control border border-line bg-surface px-3" />
  </label>
</template>
