<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchProviders, loginWithPassword, requestMagicLink, skolstreamLoginUrl } from '@/api/auth'
import { errorMessage } from '@/api/http'
import SmartCaptcha from '@/components/SmartCaptcha.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiInput from '@/components/ui/UiInput.vue'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const next = computed(() => (typeof route.query.next === 'string' ? route.query.next : '/'))

const providers = ref({ magic_link: true, skolstream: false, captcha_site_key: null })
const mode = ref('password') // password | link
const email = ref('')
const password = ref('')
const sending = ref(false)
const sentTo = ref('')
const error = ref(typeof route.query.error === 'string' ? route.query.error : '')
const fieldError = ref('')
const captchaToken = ref('')
const captcha = ref(null)

onMounted(async () => {
  try {
    providers.value = await fetchProviders()
  } catch {
    // без списка способов показываем вход по почте и паролю
  }
})

function checkEmail() {
  fieldError.value = ''
  error.value = ''
  if (!/^\S+@\S+\.\S+$/.test(email.value.trim())) {
    fieldError.value = 'Введите адрес электронной почты'
    return false
  }
  return true
}

async function submitPassword() {
  if (!checkEmail()) return
  if (!password.value) {
    error.value = 'Введите пароль'
    return
  }
  sending.value = true
  try {
    const result = await loginWithPassword(email.value.trim(), password.value, next.value)
    await auth.load(true)
    await router.replace(result.next || '/')
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    sending.value = false
  }
}

async function submitLink() {
  if (!checkEmail()) return
  if (providers.value.captcha_site_key && !captchaToken.value) {
    error.value = 'Подтвердите, что вы не робот'
    return
  }
  sending.value = true
  try {
    await requestMagicLink(email.value.trim(), next.value, captchaToken.value || null)
    sentTo.value = email.value.trim()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    sending.value = false
    captcha.value?.reset() // токен капчи одноразовый
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
        </template>

        <div class="mt-5 flex rounded-control border border-line p-1 text-sm" role="tablist" aria-label="Способ входа">
          <button
            v-for="(label, key) in { password: 'По паролю', link: 'Ссылка на почту' }"
            :key="key"
            type="button"
            role="tab"
            :aria-selected="mode === key"
            class="flex-1 rounded-[8px] px-3 py-1.5"
            :class="mode === key ? 'bg-brand-100 text-brand-700' : 'text-ink-muted hover:text-ink'"
            @click="(mode = key), (error = '')"
          >
            {{ label }}
          </button>
        </div>

        <form v-if="mode === 'password'" class="mt-4 grid gap-4" novalidate @submit.prevent="submitPassword">
          <UiInput
            v-model="email"
            label="Электронная почта"
            type="email"
            autocomplete="username"
            placeholder="name@example.ru"
            :error="fieldError"
            @input="fieldError = ''"
          />
          <UiInput v-model="password" label="Пароль" type="password" autocomplete="current-password" />
          <UiButton type="submit" variant="primary" :loading="sending">Войти</UiButton>
          <p class="text-xs text-ink-muted">Нет пароля? Войдите по ссылке на почту и задайте его в профиле или попросите организаторов.</p>
        </form>

        <form v-else class="mt-4 grid gap-4" novalidate @submit.prevent="submitLink">
          <UiInput
            v-model="email"
            label="Электронная почта"
            type="email"
            autocomplete="email"
            placeholder="name@example.ru"
            :error="fieldError"
            @input="fieldError = ''"
          />
          <SmartCaptcha v-if="providers.captcha_site_key" ref="captcha" v-model="captchaToken" :sitekey="providers.captcha_site_key" />
          <UiButton type="submit" variant="primary" :loading="sending">Получить ссылку для входа</UiButton>
        </form>
      </div>
    </div>
  </main>
</template>
