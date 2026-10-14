<script setup>
import { ref } from 'vue'
import { errorMessage } from '@/api/http'
import { DOMAIN_STATUS, DOMAIN_TONES, addDomain, checkDomain, deleteDomain } from '@/api/sites'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({
  eventId: { type: [String, Number], required: true },
  site: { type: Object, required: true },
})
const emit = defineEmits(['updated'])
const domain = ref('')
const error = ref('')
const busy = ref(false)

async function run(fn) {
  error.value = ''
  busy.value = true
  try {
    emit('updated', await fn())
    return true
  } catch (e) {
    error.value = errorMessage(e)
    return false
  } finally {
    busy.value = false
  }
}

async function add() {
  if (await run(() => addDomain(props.eventId, domain.value))) domain.value = ''
}
</script>

<template>
  <div class="grid gap-4 text-sm">
    <div class="grid gap-1">
      <span class="font-medium">Адреса сайта</span>
      <a v-for="url in site.urls" :key="url" :href="url" target="_blank" rel="noopener" class="truncate text-brand-700 hover:underline">{{ url.replace('https://', '') }}</a>
    </div>

    <div class="grid gap-2">
      <span class="font-medium">Свой домен</span>
      <p class="text-ink-muted">
        У регистратора домена создайте запись <b>CNAME</b> на <code class="rounded bg-canvas px-1">{{ site.cname_target }}</code>,
        затем добавьте домен здесь. Сертификат HTTPS выпустится сам.
      </p>
      <form class="flex gap-2" @submit.prevent="add">
        <input v-model="domain" placeholder="konkurs.school.ru" aria-label="Домен" class="h-9 min-w-0 flex-1 rounded-control border border-line bg-surface px-3" />
        <UiButton type="submit" size="sm" :loading="busy" :disabled="!domain.trim()">Добавить</UiButton>
      </form>
      <p v-if="!site.exists" class="text-ink-muted">Сначала сохраните сайт.</p>
      <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
    </div>

    <ul v-if="site.domains.length" class="grid gap-2">
      <li v-for="d in site.domains" :key="d.id" class="grid gap-1.5 rounded-control border border-line p-3">
        <div class="flex flex-wrap items-center gap-2">
          <span class="min-w-0 flex-1 truncate font-medium">{{ d.domain }}</span>
          <UiBadge :tone="DOMAIN_TONES[d.status]">{{ DOMAIN_STATUS[d.status] }}</UiBadge>
        </div>
        <p v-if="d.error" class="text-ink-muted">{{ d.error }}</p>
        <div class="flex gap-2">
          <UiButton size="sm" variant="ghost" :disabled="busy" @click="run(() => checkDomain(d.id))">Проверить</UiButton>
          <UiButton size="sm" variant="ghost" :disabled="busy" @click="run(() => deleteDomain(d.id))">Отключить</UiButton>
        </div>
      </li>
    </ul>
    <p class="text-xs text-ink-muted">DNS обновляется до суток. Ожидающие домены проверяются автоматически каждые 10 минут.</p>
  </div>
</template>
