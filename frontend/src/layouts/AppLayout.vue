<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { BrandMark, OverflowNav, SchoolFooter, UiButton } from 'sk-ui'
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
  <div class="flex min-h-dvh flex-col">
    <header v-if="!route.meta.print" class="sticky top-0 z-10 border-b border-line bg-surface/90 backdrop-blur print:hidden">
      <div class="mx-auto flex h-14 max-w-6xl items-center gap-4 px-4">
        <RouterLink :to="{ name: auth.judgeMode ? 'judging' : 'events' }" class="shrink-0">
          <BrandMark />
        </RouterLink>
        <OverflowNav v-if="links.length" :links="links">
          <template #burger-footer>
            <RouterLink :to="{ name: 'profile' }" class="grid rounded-control px-3 py-2.5 hover:bg-brand-50" active-class="bg-brand-100!" title="Профиль и пароль">
              <span class="truncate font-medium text-ink">{{ auth.displayName }}</span>
              <span class="text-xs text-ink-muted">Профиль и пароль</span>
            </RouterLink>
            <UiButton variant="ghost" class="w-full justify-start! px-3!" @click="logout">Выйти</UiButton>
          </template>
        </OverflowNav>
        <span v-else class="min-w-0 flex-1 truncate text-sm text-ink-muted">Судья: <span class="font-medium text-ink">{{ auth.displayName }}</span></span>
        <div class="shrink-0 items-center gap-3 text-sm" :class="links.length ? 'hidden sm:flex' : 'flex'">
          <RouterLink
            v-if="!auth.judgeMode"
            :to="{ name: 'profile' }"
            class="max-w-32 truncate text-ink-muted hover:text-ink lg:max-w-48"
            title="Профиль и пароль"
          >
            {{ auth.displayName }}
          </RouterLink>
          <button type="button" class="rounded-control px-3 py-1.5 hover:bg-brand-50" @click="logout">Выйти</button>
        </div>
      </div>
    </header>
    <main class="flex-1" :class="route.meta.print ? '' : 'mx-auto w-full max-w-6xl px-4 py-8'">
      <RouterView />
    </main>
    <SchoolFooter v-if="!route.meta.print" />
  </div>
</template>
