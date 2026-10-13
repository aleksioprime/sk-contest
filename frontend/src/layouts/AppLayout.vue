<script setup>
import { RouterLink, RouterView } from 'vue-router'

const links = [
  { to: { name: 'home' }, label: 'Состояние' },
  { to: { name: 'ui-kit' }, label: 'Компоненты' },
]
</script>

<template>
  <div class="min-h-dvh">
    <header class="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur">
      <div class="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <RouterLink :to="{ name: 'home' }" class="flex items-center gap-2 font-semibold">
          <img src="/favicon.svg" alt="" class="size-7" />
          SK Events
        </RouterLink>
        <nav class="flex gap-1 text-sm" aria-label="Основное меню">
          <RouterLink
            v-for="link in links"
            :key="link.label"
            :to="link.to"
            class="rounded-control px-3 py-1.5 text-ink-muted hover:bg-brand-50 hover:text-ink"
            exact-active-class="!bg-brand-100 !text-brand-700"
          >
            {{ link.label }}
          </RouterLink>
        </nav>
      </div>
    </header>
    <main class="mx-auto max-w-6xl px-4 py-8">
      <RouterView />
    </main>
  </div>
</template>
