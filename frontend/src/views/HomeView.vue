<script setup>
import { onMounted } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import { useSystemStore } from '@/stores/system'

const system = useSystemStore()
onMounted(system.load)

const labels = { database: 'PostgreSQL', redis: 'Redis' }
</script>

<template>
  <div class="grid gap-6">
    <div>
      <h1 class="text-2xl font-bold">Платформа мероприятий</h1>
      <p class="mt-1 text-ink-muted">Этап 0: каркас приложения. Здесь видно, что frontend, API и инфраструктура связаны.</p>
    </div>

    <p v-if="system.error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ system.error }}</p>

    <div class="grid gap-4 sm:grid-cols-2">
      <UiCard>
        <template #title>API</template>
        <dl v-if="system.meta" class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt class="text-ink-muted">Версия</dt>
          <dd>{{ system.meta.version }}</dd>
          <dt class="text-ink-muted">Окружение</dt>
          <dd>{{ system.meta.environment }}</dd>
          <dt class="text-ink-muted">Домен лендингов</dt>
          <dd>*.{{ system.meta.sites_base_domain }}</dd>
        </dl>
        <p v-else class="text-sm text-ink-muted">Загрузка…</p>
      </UiCard>

      <UiCard>
        <template #title>Зависимости</template>
        <ul v-if="system.readiness" class="grid gap-2 text-sm">
          <li v-for="(ok, name) in system.readiness.checks" :key="name" class="flex items-center justify-between">
            {{ labels[name] ?? name }}
            <UiBadge :tone="ok ? 'success' : 'danger'">{{ ok ? 'доступен' : 'недоступен' }}</UiBadge>
          </li>
        </ul>
        <p v-else class="text-sm text-ink-muted">Загрузка…</p>
      </UiCard>
    </div>

    <div><UiButton @click="system.load">Обновить</UiButton></div>
  </div>
</template>
