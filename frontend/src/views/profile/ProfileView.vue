<script setup>
import { ref } from 'vue'
import { changePassword } from '@/api/auth'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const current = ref('')
const next = ref('')
const repeat = ref('')
const error = ref('')
const notice = ref('')
const saving = ref(false)

async function save() {
  error.value = ''
  notice.value = ''
  if (next.value.length < 8) {
    error.value = 'Пароль должен быть не короче 8 символов'
    return
  }
  if (next.value !== repeat.value) {
    error.value = 'Пароли не совпадают'
    return
  }
  saving.value = true
  try {
    await changePassword(current.value, next.value)
    notice.value = 'Пароль сохранён. Теперь можно входить по email и паролю.'
    current.value = next.value = repeat.value = ''
    await auth.load(true)
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="grid max-w-xl gap-6">
    <div>
      <h1 class="text-2xl font-bold">Профиль</h1>
      <p class="mt-1 text-ink-muted">{{ auth.user?.person?.full_name || auth.displayName }} · {{ auth.user?.email }}</p>
    </div>
    <UiCard>
      <template #title>{{ auth.hasPassword ? 'Сменить пароль' : 'Задать пароль' }}</template>
      <form class="grid gap-4" @submit.prevent="save">
        <UiInput v-if="auth.hasPassword" v-model="current" label="Текущий пароль" type="password" autocomplete="current-password" />
        <UiInput v-model="next" label="Новый пароль" type="password" autocomplete="new-password" hint="Не короче 8 символов" />
        <UiInput v-model="repeat" label="Повторите пароль" type="password" autocomplete="new-password" />
        <p v-if="error" role="alert" class="rounded-control bg-red-100 px-3 py-2 text-sm text-red-800">{{ error }}</p>
        <p v-if="notice" role="status" class="rounded-control bg-green-100 px-3 py-2 text-sm text-green-800">{{ notice }}</p>
        <UiButton type="submit" variant="primary" :loading="saving" class="justify-self-start">Сохранить пароль</UiButton>
      </form>
    </UiCard>
  </div>
</template>
