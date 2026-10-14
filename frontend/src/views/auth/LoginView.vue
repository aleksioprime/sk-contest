<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { fetchProviders, requestMagicLink, skolstreamLoginUrl } from '@/api/auth'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'

const route = useRoute()
const next = computed(() => (typeof route.query.next === 'string' ? route.query.next : '/'))

const providers = ref({ magic_link: true, skolstream: false })
const email = ref('')
const sending = ref(false)
const sentTo = ref('')
const error = ref(typeof route.query.error === 'string' ? route.query.error : '')
const fieldError = ref('')

onMounted(async () => {
  try {
    providers.value = await fetchProviders()
  } catch {
    // без списка способов показываем только вход по почте
  }
})

async function submit() {
  fieldError.value = ''
  error.value = ''
  if (!/^\S+@\S+\.\S+$/.test(email.value.trim())) {
    fieldError.value = 'Введите адрес электронной почты'
    return
  }
  sending.value = true
  try {
    await requestMagicLink(email.value.trim(), next.value)
    sentTo.value = email.value.trim()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    sending.value = false
  }
}
</script>

<template>
  <main class="grid min-h-dvh place-items-center px-4 py-10">
    <div class="w-full max-w-sm">
      <div class="mb-8 flex items-center gap-2 text-lg font-semibold">
        <img src="/favicon.svg" alt="" class="size-8" />
        SK Events
      </div>

      <div v-if="sentTo" class="rounded-card border border-line bg-surface p-6">
        <h1 class="text-xl font-bold">Проверьте почту</h1>
        <p class="mt-2 text-ink-muted">
          Мы отправили ссылку для входа на <span class="font-medium text-ink">{{ sentTo }}</span>. Она действует
          20 минут.
        </p>
        <UiButton class="mt-5" variant="ghost" @click="sentTo = ''">Указать другой адрес</UiButton>
      </div>

      <div v-else class="rounded-card border border-line bg-surface p-6">
        <h1 class="text-xl font-bold">Вход</h1>
        <p class="mt-1 text-sm text-ink-muted">Для участников, судей и организаторов мероприятий.</p>

        <p v-if="error" role="alert" class="mt-4 rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>

        <template v-if="providers.skolstream">
          <a
            :href="skolstreamLoginUrl(next)"
            class="mt-5 flex h-10 items-center justify-center rounded-control bg-brand-600 font-medium text-white hover:bg-brand-700"
          >
            Войти через SkolStream
          </a>
          <p class="mt-2 text-center text-xs text-ink-muted">Для учеников и сотрудников гимназии</p>
          <div class="my-5 flex items-center gap-3 text-xs text-ink-muted">
            <span class="h-px flex-1 bg-line" />или по почте<span class="h-px flex-1 bg-line" />
          </div>
        </template>

        <form class="grid gap-4" :class="{ 'mt-5': !providers.skolstream }" novalidate @submit.prevent="submit">
          <UiInput
            v-model="email"
            label="Электронная почта"
            type="email"
            autocomplete="email"
            placeholder="name@example.ru"
            :error="fieldError"
            @input="fieldError = ''"
          />
          <UiButton type="submit" :variant="providers.skolstream ? 'secondary' : 'primary'" :loading="sending">
            Получить ссылку для входа
          </UiButton>
        </form>
      </div>
    </div>
  </main>
</template>
