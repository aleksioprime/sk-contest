<script setup>
/** Открытая форма заявки: первый шаг для посетителя без входа и для вошедшего пользователя. */
import { computed, onMounted, reactive, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { fetchMyApplications, fetchPublicForm, fieldErrors, isVisible, registerForEvent } from '@/api/applications'
import { fetchProviders } from '@/api/auth'
import { errorMessage } from '@/api/http'
import ConsentsList from '@/components/applications/ConsentsList.vue'
import FieldInput from '@/components/applications/FieldInput.vue'
import BrandMark from '@/components/brand/BrandMark.vue'
import SchoolFooter from '@/components/brand/SchoolFooter.vue'
import SmartCaptcha from '@/components/SmartCaptcha.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'
import { useAuthStore } from '@/stores/auth'
import { formatRange } from '@/utils/dates'

const props = defineProps({ slug: { type: String, required: true } })
const route = useRoute()
const auth = useAuthStore()

const schema = ref(null)
const existing = ref([])
const loadError = ref('')
const draft = reactive({
  full_name: '',
  email: '',
  phone: '',
  organization: '',
  grade: '',
  title: '',
  direction_id: null,
  participation_form_id: null,
  answers: {},
  consents: [],
})
const errors = ref({})
const message = ref('')
const sending = ref(false)
const result = ref(null)
const captchaKey = ref(null)
const captchaToken = ref('')
const captcha = ref(null)

const settings = computed(() => schema.value?.form.registration)
const isAsked = (name) => settings.value.asked.includes(name)
const questions = computed(() => schema.value.form.fields.filter((f) => f.on_registration && isVisible(f, draft.answers)))
const needsLogin = computed(() => !auth.isAuthenticated && !settings.value.open_form)
const loginLink = computed(() => ({ name: 'login', query: { next: route.fullPath } }))
const dates = computed(() => formatRange(schema.value.event.date_start, schema.value.event.date_end))

async function send() {
  sending.value = true
  errors.value = {}
  message.value = ''
  try {
    result.value = await registerForEvent(props.slug, { ...draft, captcha_token: captchaToken.value || null })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  } catch (e) {
    errors.value = fieldErrors(e)
    message.value = errorMessage(e)
    captcha.value?.reset()
  } finally {
    sending.value = false
  }
}

onMounted(async () => {
  try {
    schema.value = await fetchPublicForm(props.slug)
    if (auth.isAuthenticated) {
      existing.value = (await fetchMyApplications()).filter((a) => a.event.slug === props.slug && a.status !== 'withdrawn')
    } else {
      captchaKey.value = (await fetchProviders()).captcha_site_key
    }
  } catch (e) {
    loadError.value = errorMessage(e)
  }
})
</script>

<template>
  <div class="flex min-h-dvh flex-col">
    <header class="border-b border-line bg-surface">
      <div class="mx-auto flex h-14 max-w-2xl items-center justify-between gap-4 px-4">
        <BrandMark />
        <RouterLink v-if="auth.isAuthenticated" :to="{ name: 'my-applications' }" class="text-sm text-ink-muted hover:text-ink">Мои заявки</RouterLink>
        <RouterLink v-else :to="loginLink" class="text-sm text-ink-muted hover:text-ink">Войти</RouterLink>
      </div>
    </header>

    <main class="mx-auto grid w-full max-w-2xl flex-1 content-start gap-6 px-4 py-8">
      <p v-if="loadError" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ loadError }}</p>
      <SkeletonPage v-else-if="!schema" :cards="2" />

      <template v-else>
        <img v-if="schema.event.cover_url" :src="schema.event.cover_url" alt="" class="h-48 w-full rounded-card object-cover" />
        <div>
          <h1 class="text-2xl font-bold">{{ schema.event.title }}</h1>
          <p v-if="dates || schema.event.place" class="mt-1 text-sm text-ink-muted">
            {{ [dates, schema.event.place].filter(Boolean).join(' · ') }}
          </p>
          <p v-if="schema.event.short_description" class="mt-3">{{ schema.event.short_description }}</p>
        </div>

        <div v-if="result" role="status" class="grid gap-2 rounded-card border border-green-300 bg-green-50 p-5 text-green-900">
          <p class="font-semibold">Спасибо!</p>
          <p class="whitespace-pre-line">{{ result.message }}</p>
          <RouterLink v-if="result.application_id" :to="{ name: 'application', params: { id: result.application_id } }" class="font-medium underline">
            Открыть заявку
          </RouterLink>
        </div>

        <template v-else>
          <div v-if="existing.length" class="rounded-card border border-line bg-surface p-4 text-sm">
            <p>У вас уже есть заявки на это мероприятие:</p>
            <ul class="mt-2 grid gap-1">
              <li v-for="app in existing" :key="app.id">
                <RouterLink :to="{ name: 'application', params: { id: app.id } }" class="font-medium text-brand-700 hover:underline">
                  Заявка №{{ app.number }}{{ app.title ? ` · ${app.title}` : '' }}
                </RouterLink>
              </li>
            </ul>
          </div>

          <p v-if="!schema.registration_open" class="rounded-control bg-canvas px-4 py-3 text-ink-muted">Приём заявок сейчас закрыт.</p>

          <div v-else-if="needsLogin" class="grid gap-3 rounded-card border border-line bg-surface p-5">
            <p>Заявку на это мероприятие можно подать только из личного кабинета.</p>
            <div><RouterLink :to="loginLink" class="font-medium text-brand-700 hover:underline">Войти, чтобы подать заявку</RouterLink></div>
          </div>

          <form v-else class="grid gap-6" novalidate @submit.prevent="send">
            <p v-if="settings.intro" class="whitespace-pre-line">{{ settings.intro }}</p>
            <p class="text-sm text-ink-muted">
              Это общая заявка. Когда организаторы её подтвердят, на почту придёт приглашение
              {{ settings.details_step ? 'заполнить остальное в личном кабинете' : 'на мероприятие' }}.
            </p>

            <UiCard>
              <template #title>О вас</template>
              <div class="grid gap-4">
                <template v-if="auth.isAuthenticated">
                  <p class="text-sm">Вы вошли как <span class="font-medium">{{ auth.displayName }}</span><template v-if="auth.displayName !== auth.user.email">, {{ auth.user.email }}</template>. Заявка появится в вашем кабинете.</p>
                </template>
                <template v-else>
                  <p class="text-sm text-ink-muted">
                    Участвовали раньше или есть учётная запись SkolStream?
                    <RouterLink :to="loginLink" class="font-medium text-brand-700 hover:underline">Войдите</RouterLink>,
                    чтобы заявка сразу попала в ваш кабинет.
                  </p>
                  <UiInput v-model="draft.full_name" label="Фамилия и имя *" autocomplete="name" :error="errors.full_name" />
                  <UiInput v-model="draft.email" type="email" label="Email *" autocomplete="email" hint="На этот адрес придёт приглашение" :error="errors.email" />
                </template>
                <UiInput v-if="isAsked('phone')" v-model="draft.phone" type="tel" label="Телефон" placeholder="+7 900 000-00-00" autocomplete="tel" :error="errors.phone" />
                <UiInput v-if="isAsked('organization')" v-model="draft.organization" label="Школа или организация" :error="errors.organization" />
                <UiInput v-if="isAsked('grade')" v-model="draft.grade" label="Класс" :error="errors.grade" />
              </div>
            </UiCard>

            <UiCard v-if="isAsked('title') || (isAsked('direction') && schema.directions.length) || (isAsked('participation_form') && schema.participation_forms.length) || questions.length">
              <template #title>Об участии</template>
              <div class="grid gap-4">
                <UiInput v-if="isAsked('title')" v-model="draft.title" label="Название работы *" :error="errors.title" />
                <label v-if="isAsked('direction') && schema.directions.length" class="grid gap-1.5 text-sm">
                  <span class="font-medium">Направление *</span>
                  <UiSelect v-model="draft.direction_id" :invalid="!!errors.direction_id">
                    <option :value="null">Не выбрано</option>
                    <option v-for="d in schema.directions" :key="d.id" :value="d.id">{{ d.title }}</option>
                  </UiSelect>
                  <span v-if="errors.direction_id" class="text-red-600">{{ errors.direction_id }}</span>
                </label>
                <label v-if="isAsked('participation_form') && schema.participation_forms.length" class="grid gap-1.5 text-sm">
                  <span class="font-medium">Форма участия *</span>
                  <UiSelect v-model="draft.participation_form_id" :invalid="!!errors.participation_form_id">
                    <option :value="null">Не выбрано</option>
                    <option v-for="f in schema.participation_forms" :key="f.id" :value="f.id">{{ f.title }}</option>
                  </UiSelect>
                  <span v-if="errors.participation_form_id" class="text-red-600">{{ errors.participation_form_id }}</span>
                </label>
                <FieldInput v-for="field in questions" :key="field.key" v-model="draft.answers[field.key]" :field="field" :error="errors[field.key]" />
              </div>
            </UiCard>

            <UiCard v-if="schema.form.consents.length">
              <template #title>Согласия</template>
              <ConsentsList v-model="draft.consents" :consents="schema.form.consents" :errors="errors" />
            </UiCard>

            <SmartCaptcha v-if="captchaKey" ref="captcha" v-model="captchaToken" :sitekey="captchaKey" />
            <p v-if="message" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ message }}</p>
            <div><UiButton type="submit" variant="primary" :loading="sending">Отправить заявку</UiButton></div>
          </form>
        </template>
      </template>
    </main>
    <SchoolFooter />
  </div>
</template>
