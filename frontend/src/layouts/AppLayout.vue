<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

const links = computed(() => [
  { to: { name: 'events' }, label: 'Мероприятия' },
  { to: { name: 'my-applications' }, label: 'Мои заявки' },
  { to: { name: 'judging' }, label: 'Оценивание' },
  ...(auth.isAdmin
    ? [
        { to: { name: 'admin-people' }, label: 'Люди' },
        { to: { name: 'system' }, label: 'Состояние' },
      ]
    : []),
])

async function logout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="min-h-dvh">
    <header class="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur">
      <div class="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <RouterLink :to="{ name: 'home' }" class="flex items-center gap-2 font-semibold">
          <img src="/favicon.svg" alt="" class="size-7" />
          <span class="hidden sm:inline">SK Events</span>
        </RouterLink>
        <nav class="flex gap-1 overflow-x-auto text-sm" aria-label="Основное меню">
          <RouterLink
            v-for="link in links"
            :key="link.label"
            :to="link.to"
            class="whitespace-nowrap rounded-control px-3 py-1.5 text-ink-muted hover:bg-brand-50 hover:text-ink"
            active-class="!bg-brand-100 !text-brand-700"
          >
            {{ link.label }}
          </RouterLink>
        </nav>
        <div class="ml-auto flex items-center gap-3 text-sm">
          <span class="hidden truncate text-ink-muted md:inline">{{ auth.displayName }}</span>
          <button type="button" class="rounded-control px-3 py-1.5 hover:bg-brand-50" @click="logout">Выйти</button>
        </div>
      </div>
    </header>
    <main class="mx-auto max-w-6xl px-4 py-8">
      <RouterView />
    </main>
  </div>
</template>
