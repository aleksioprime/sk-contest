<script setup>
import UiSkeleton from './UiSkeleton.vue'

defineProps({ rows: { type: Number, default: 3 } })
</script>

<template>
  <ul class="grid gap-3" aria-busy="true" aria-label="Загрузка">
    <li v-for="row in rows" :key="row" class="flex items-center gap-4 rounded-card border border-line bg-surface p-4">
      <div class="grid flex-1 gap-2">
        <UiSkeleton class="h-4 w-2/5" />
        <UiSkeleton class="h-3 w-3/5" />
      </div>
      <UiSkeleton class="h-6 w-20 rounded-full" />
    </li>
  </ul>
</template>
