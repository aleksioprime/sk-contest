<script setup>
import { blocks } from '@sk-events/blocks'

const emit = defineEmits(['add', 'close'])
</script>

<template>
  <div class="fixed inset-0 z-40 grid place-items-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-label="Добавить блок" @click.self="emit('close')">
    <div class="grid max-h-[85vh] w-full max-w-3xl gap-4 overflow-y-auto rounded-card bg-surface p-6 shadow-xl">
      <div class="flex items-center justify-between">
        <p class="text-lg font-semibold">Добавить блок</p>
        <button type="button" class="rounded px-2 text-xl text-ink-muted hover:bg-brand-50" aria-label="Закрыть" @click="emit('close')">×</button>
      </div>
      <ul class="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        <li v-for="block in blocks" :key="block.type">
          <button type="button" class="grid h-full w-full gap-1 rounded-card border border-line p-4 text-left hover:border-brand-300 hover:bg-brand-50" @click="emit('add', block.type)">
            <span class="font-medium">{{ block.title }}</span>
            <span class="text-sm text-ink-muted">{{ block.description }}</span>
          </button>
        </li>
      </ul>
    </div>
  </div>
</template>
