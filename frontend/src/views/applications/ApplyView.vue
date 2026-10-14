<script setup>
/** Переход «Подать заявку» с лендинга: открывает текущую заявку или создаёт черновик. */
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { fetchMyApplications, fetchPublicForm, startApplication } from '@/api/applications'
import { errorMessage } from '@/api/http'
import UiButton from '@/components/ui/UiButton.vue'
import SkeletonPage from '@/components/skeleton/SkeletonPage.vue'

const props = defineProps({ slug: { type: String, required: true } })
const router = useRouter()
const schema = ref(null)
const existing = ref([])
const error = ref('')
const starting = ref(false)

async function start() {
  starting.value = true
  error.value = ''
  try {
    const app = await startApplication(props.slug)
    await router.replace({ name: 'application', params: { id: app.id } })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    starting.value = false
  }
}

onMounted(async () => {
  try {
    schema.value = await fetchPublicForm(props.slug)
    const mine = (await fetchMyApplications()).filter((a) => a.event.slug === props.slug && a.status !== 'withdrawn')
    const editable = mine.find((a) => a.can_edit)
    if (editable) {
      await router.replace({ name: 'application', params: { id: editable.id } })
      return
    }
    existing.value = mine
    if (!mine.length && schema.value.registration_open) await start()
  } catch (e) {
    error.value = errorMessage(e)
  }
})
</script>

<template>
  <div class="grid max-w-xl gap-4">
    <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
    <template v-else-if="schema">
      <h1 class="text-2xl font-bold">{{ schema.event.title }}</h1>
      <p v-if="!schema.registration_open" class="text-ink-muted">Приём заявок сейчас закрыт.</p>
      <template v-if="existing.length">
        <p>У вас уже есть заявки на это мероприятие:</p>
        <ul class="grid gap-2">
          <li v-for="app in existing" :key="app.id">
            <RouterLink :to="{ name: 'application', params: { id: app.id } }" class="font-medium text-brand-700">
              Заявка №{{ app.number }}{{ app.title ? ` · ${app.title}` : '' }}
            </RouterLink>
          </li>
        </ul>
        <div v-if="schema.registration_open">
          <UiButton :loading="starting" @click="start">Подать ещё одну заявку</UiButton>
        </div>
      </template>
    </template>
    <SkeletonPage v-else :cards="1" />
  </div>
</template>
