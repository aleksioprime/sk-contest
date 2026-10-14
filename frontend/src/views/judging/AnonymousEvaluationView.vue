<script setup>
/** Оценка работы зрителем по QR-коду, без входа. Токен оценки хранится в браузере. */
import { onMounted, ref } from 'vue'
import { anonymousClient, fetchPublicWork, readAnonymousToken, startAnonymous } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import EvaluationForm from '@/components/evaluation/EvaluationForm.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

const props = defineProps({ token: { type: String, required: true } })
const work = ref(null)
const bundle = ref(null)
const client = ref(null)
const name = ref('')
const error = ref('')
const starting = ref(false)

onMounted(async () => {
  try {
    work.value = await fetchPublicWork(props.token)
    const saved = readAnonymousToken(props.token)
    if (saved) {
      client.value = anonymousClient(props.token, saved)
      bundle.value = await client.value.load().catch(() => null)
    }
  } catch (e) {
    error.value = e?.response?.status === 404 ? 'Работа не найдена или оценка по ссылке не предусмотрена.' : errorMessage(e)
  }
})

async function start() {
  starting.value = true
  error.value = ''
  try {
    const started = await startAnonymous(props.token, name.value)
    client.value = anonymousClient(props.token, started.token)
    bundle.value = started.evaluation
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    starting.value = false
  }
}
</script>

<template>
  <main class="mx-auto grid max-w-2xl gap-6 px-4 py-8">
    <div class="flex items-center gap-2 font-semibold">
      <img src="/favicon.svg" alt="" class="size-7" />
      SK Events
    </div>
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <p v-else-if="!work" class="text-ink-muted">Загрузка…</p>

    <template v-if="work">
      <div>
        <p class="text-sm text-ink-muted">{{ work.event_title }} · {{ work.sheet_title }}</p>
        <h1 class="mt-1 text-2xl font-bold">{{ work.work.title || 'Работа' }}</h1>
        <p class="mt-1 text-ink-muted">{{ work.work.participants.join(', ') }}<span v-if="work.work.direction"> · {{ work.work.direction }}</span></p>
      </div>

      <EvaluationForm v-if="bundle && client" v-model:bundle="bundle" :client="client" />
      <p v-else-if="!work.open" class="rounded-control bg-canvas px-4 py-3 text-ink-muted">Оценка этой работы закрыта.</p>
      <form v-else class="grid gap-4 rounded-card border border-line bg-surface p-5" @submit.prevent="start">
        <p>Оцените работу по критериям. Ваша оценка анонимна.</p>
        <UiInput v-model="name" label="Как к вам обращаться" placeholder="Можно не заполнять" maxlength="100" />
        <UiButton type="submit" variant="primary" :loading="starting">Начать оценку</UiButton>
      </form>
      <p v-if="bundle?.is_scored" class="rounded-control bg-green-100 px-4 py-3 text-green-800" role="status">Спасибо! Оценка сохранена.</p>
    </template>
  </main>
</template>
