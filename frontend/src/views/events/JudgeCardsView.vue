<script setup>
/** Листы судей для печати: на каждого судью страница с QR для входа. Ссылки одноразовые и действуют 20 минут. */
import QRCode from 'qrcode'
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { fetchSheet, issueJudgeCards } from '@/api/evaluation'
import { fetchEvent } from '@/api/events'
import { errorMessage } from '@/api/http'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({ id: { type: String, required: true }, sheetId: { type: String, required: true } })
const route = useRoute()
const cards = ref([])
const sheet = ref(null)
const event = ref(null)
const error = ref('')
const loading = ref(true)

const userIds = computed(() => (route.query.user ? [route.query.user].flat().map(Number) : null))
const time = (value) => new Date(value).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })

async function issue() {
  loading.value = true
  error.value = ''
  try {
    ;[sheet.value, event.value] = await Promise.all([fetchSheet(props.sheetId), fetchEvent(props.id)])
    const issued = await issueJudgeCards(props.sheetId, userIds.value)
    cards.value = await Promise.all(
      issued.map(async (card) => ({ ...card, qr: await QRCode.toDataURL(card.login_url, { width: 360, margin: 1 }) })),
    )
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

function print() {
  window.print()
}

onMounted(issue)
</script>

<template>
  <div class="mx-auto max-w-3xl px-4 py-6 print:max-w-none print:p-0">
    <div class="mb-6 flex flex-wrap items-center gap-3 print:hidden">
      <RouterLink :to="{ name: 'event-sheet', params: { id, sheetId } }" class="text-sm text-ink-muted hover:text-ink">← К листу</RouterLink>
      <span class="flex-1" />
      <UiButton :loading="loading" @click="issue">Выпустить новые QR</UiButton>
      <UiButton variant="primary" :disabled="!cards.length" @click="print">Печать</UiButton>
    </div>
    <p class="mb-6 rounded-control bg-amber-50 px-4 py-3 text-sm text-amber-900 print:hidden">
      Каждый QR действует 20 минут с момента выпуска и только для одного входа. Печатайте листы непосредственно перед раздачей судьям.
    </p>

    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <SkeletonPage v-else-if="loading" :cards="2" />
    <p v-else-if="!cards.length" class="text-ink-muted">В листе нет судей.</p>

    <article
      v-for="card in cards"
      :key="card.user_id"
      class="mb-8 grid break-after-page gap-6 rounded-card border border-line bg-white p-10 text-[#1d1a2b] print:mb-0 print:min-h-screen print:rounded-none print:border-0"
    >
      <header>
        <p class="text-sm uppercase tracking-wider text-[#5f5a75]">Лист судьи</p>
        <h1 class="mt-1 text-3xl font-bold">{{ card.full_name }}</h1>
        <p class="mt-2 text-lg">{{ event?.title }}</p>
        <p class="text-[#5f5a75]">{{ sheet?.title }} · работ для оценки: {{ card.works }}</p>
      </header>
      <div class="flex flex-wrap items-center gap-8">
        <img :src="card.qr" alt="QR-код для входа" class="size-64" />
        <ol class="grid max-w-sm list-decimal gap-2 pl-5 text-lg">
          <li>Откройте камеру телефона и наведите её на QR-код.</li>
          <li>Перейдите по ссылке: вход выполнится автоматически.</li>
          <li>Оценивайте работы по критериям — всё сохраняется сразу.</li>
        </ol>
      </div>
      <p class="rounded-control border-2 border-[#b45309] px-4 py-3 text-lg font-semibold text-[#b45309]">
        Вход действует до {{ time(card.expires_at) }} — 20 минут с момента печати, один раз.
      </p>
      <p class="text-sm text-[#5f5a75]">Если время вышло, попросите модератора выпустить новый QR.</p>
    </article>
  </div>
</template>
