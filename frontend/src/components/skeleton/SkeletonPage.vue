<script setup>
import UiSkeleton from './UiSkeleton.vue'

defineProps({ cards: { type: Number, default: 2 } })
</script>

<template>
  <div class="grid gap-6" aria-busy="true" aria-label="Загрузка">
    <div class="grid gap-2">
      <UiSkeleton class="h-3 w-24" />
      <UiSkeleton class="h-7 w-1/2" />
      <UiSkeleton class="h-4 w-1/3" />
    </div>
    <div v-for="card in cards" :key="card" class="grid gap-3 rounded-card border border-line bg-surface p-5">
      <UiSkeleton class="h-5 w-40" />
      <UiSkeleton class="h-10 w-full" />
      <UiSkeleton class="h-10 w-full" />
      <UiSkeleton class="h-10 w-2/3" />
    </div>
  </div>
</template>
