<script setup>
import UiSkeleton from './UiSkeleton.vue'

defineProps({ rows: { type: Number, default: 5 }, columns: { type: Number, default: 4 } })
</script>

<template>
  <div class="grid gap-0" aria-busy="true" aria-label="Загрузка">
    <div v-for="row in rows" :key="row" class="flex gap-4 border-t border-line px-4 py-3 first:border-t-0">
      <UiSkeleton v-for="column in columns" :key="column" class="h-4" :class="column === 2 ? 'flex-[2]' : 'flex-1'" />
    </div>
  </div>
</template>
