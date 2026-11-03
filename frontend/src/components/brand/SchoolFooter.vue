<script setup>
/** Футер: ссылка на хаб приложений гимназии и на её сайт. */
import { HUB, SCHOOL } from '@/brand'

const year = new Date().getFullYear()
</script>

<template>
  <footer class="border-t border-line bg-surface/60 print:hidden">
    <div class="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-5 text-sm">
      <a :href="HUB.url" class="flex items-center gap-2 font-medium hover:text-brand-700">
        <img src="/gymnasium-logo.svg" alt="" class="size-6" />
        {{ HUB.name }}
      </a>
      <span class="text-ink-muted sm:ml-auto">
        © {{ year }} ·
        <a :href="SCHOOL.url" target="_blank" rel="noopener" class="hover:text-ink">gymnasium.sk.ru</a>
      </span>
    </div>
  </footer>
</template>
