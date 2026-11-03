<script setup>
/** Логотип и название сервиса с подписью гимназии. Логотип гимназии — в футере. */
import { SCHOOL, SERVICE_NAME } from '@/brand'

defineProps({
  size: { type: String, default: 'md' }, // md — шапка, lg — страница входа
})
</script>

<template>
  <span class="flex items-center gap-2.5">
    <img src="/favicon.svg" alt="" :class="size === 'lg' ? 'size-11' : 'size-8'" />
    <span class="grid leading-tight">
      <span class="font-bold" :class="size === 'lg' ? 'text-xl' : 'text-base'">{{ SERVICE_NAME }}</span>
      <span class="text-xs text-ink-muted">{{ SCHOOL.name }}</span>
    </span>
  </span>
</template>
