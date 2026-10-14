<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import OverflowNav from '@/components/OverflowNav.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const links = computed(() =>
  auth.judgeMode
    ? []
    : [
        { to: { name: 'events' }, label: 'Мероприятия' },
        { to: { name: 'my-applications' }, label: 'Мои заявки' },
        { to: { name: 'judging' }, label: 'Оценивание' },
        ...(auth.isAdmin
          ? [
              { to: { name: 'admin-people' }, label: 'Люди' },
              { to: { name: 'system' }, label: 'Состояние' },
            ]
          : []),
      ],
)

async function logout() {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="min-h-dvh">
    <header v-if="!route.meta.print && !route.meta.bare" class="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur print:hidden">
      <div class="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <RouterLink :to="{ name: auth.judgeMode ? 'judging' : 'events' }" class="flex shrink-0 items-center gap-2 font-semibold">
          <img src="/favicon.svg" alt="" class="size-7" />
          <span class="hidden sm:inline">SK Events</span>
        </RouterLink>
        <OverflowNav v-if="links.length" :links="links" />
        <span v-else class="min-w-0 flex-1 truncate text-sm text-ink-muted">Судья: <span class="font-medium text-ink">{{ auth.displayName }}</span></span>
        <div class="flex shrink-0 items-center gap-3 text-sm">
          <RouterLink
            v-if="!auth.judgeMode"
            :to="{ name: 'profile' }"
            class="hidden max-w-48 truncate text-ink-muted hover:text-ink md:inline"
            title="Профиль и пароль"
          >
            {{ auth.displayName }}
          </RouterLink>
          <button type="button" class="rounded-control px-3 py-1.5 hover:bg-brand-50" @click="logout">Выйти</button>
        </div>
      </div>
    </header>
    <main :class="route.meta.print || route.meta.bare ? '' : 'mx-auto max-w-6xl px-4 py-8'">
      <RouterView />
    </main>
  </div>
</template>
