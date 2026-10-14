<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { judgeClient } from '@/api/evaluation'
import { errorMessage } from '@/api/http'
import EvaluationForm from '@/components/evaluation/EvaluationForm.vue'

const props = defineProps({ id: { type: String, required: true } })
const bundle = ref(null)
const error = ref('')
const client = computed(() => judgeClient(props.id))

async function load() {
  error.value = ''
  bundle.value = null
  try {
    bundle.value = await client.value.load()
  } catch (e) {
    error.value = errorMessage(e)
  }
}

watch(() => props.id, load, { immediate: true })
</script>

<template>
  <p v-if="error" role="alert" class="rounded-control bg-red-100 px-4 py-3 text-red-800">{{ error }}</p>
  <p v-else-if="!bundle" class="text-ink-muted">Загрузка…</p>

  <div v-else class="grid max-w-3xl gap-6">
    <div>
      <RouterLink :to="{ name: 'judge-sheet', params: { id: bundle.sheet_id } }" class="text-sm text-ink-muted hover:text-ink">
        ← {{ bundle.sheet_title }}
      </RouterLink>
      <h1 class="mt-2 text-2xl font-bold">№{{ bundle.work.number }} · {{ bundle.work.title || 'Без названия' }}</h1>
      <p class="mt-1 text-ink-muted">
        {{ bundle.work.participants.join(', ') }}
        <span v-if="bundle.work.direction"> · {{ bundle.work.direction }}</span>
        <span v-if="bundle.work.participation_form"> · {{ bundle.work.participation_form }}</span>
      </p>
    </div>

    <details class="rounded-card border border-line bg-surface p-4" :open="!bundle.items.length">
      <summary class="cursor-pointer font-semibold">О работе</summary>
      <dl class="mt-3 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-[180px_1fr]">
        <template v-if="bundle.work.supervisors.length">
          <dt class="text-ink-muted">Руководители</dt>
          <dd>{{ bundle.work.supervisors.join(', ') }}</dd>
        </template>
        <template v-for="answer in bundle.work.answers" :key="answer.label">
          <dt class="text-ink-muted">{{ answer.label }}</dt>
          <dd class="whitespace-pre-line">{{ Array.isArray(answer.value) ? answer.value.join(', ') : answer.value }}</dd>
        </template>
        <template v-if="bundle.work.files.length">
          <dt class="text-ink-muted">Файлы</dt>
          <dd><a v-for="file in bundle.work.files" :key="file.url" :href="file.url" target="_blank" class="block text-brand-700 hover:underline">{{ file.name }}</a></dd>
        </template>
      </dl>
    </details>

    <EvaluationForm v-model:bundle="bundle" :client="client" />

    <nav class="flex justify-between gap-3" aria-label="Соседние работы">
      <RouterLink v-if="bundle.prev_id" :to="{ name: 'judge-evaluation', params: { id: bundle.prev_id } }" class="rounded-control border border-line bg-surface px-4 py-2 hover:bg-brand-50">← Предыдущая</RouterLink>
      <span v-else />
      <RouterLink v-if="bundle.next_id" :to="{ name: 'judge-evaluation', params: { id: bundle.next_id } }" class="rounded-control bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700">Следующая работа →</RouterLink>
      <RouterLink v-else :to="{ name: 'judge-sheet', params: { id: bundle.sheet_id } }" class="rounded-control bg-brand-600 px-4 py-2 font-medium text-white hover:bg-brand-700">К списку работ</RouterLink>
    </nav>
  </div>
</template>
