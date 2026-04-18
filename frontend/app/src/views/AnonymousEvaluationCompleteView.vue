<script setup>
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import publicApi from '../api/public'

const props = defineProps({
  token: { type: String, required: true },
})

const router = useRouter()
const loading = ref(true)

const COMPLETION_STORAGE_KEY_PREFIX = 'sk_contest_anonymous_completed_'

function completionStorageKey(token) {
  return `${COMPLETION_STORAGE_KEY_PREFIX}${token}`
}

function getCompletionMarker(token) {
  try {
    const raw = window.localStorage.getItem(completionStorageKey(token))
    if (!raw) return null

    try {
      const parsed = JSON.parse(raw)
      if (parsed && typeof parsed === 'object') {
        return parsed
      }
    } catch {
      // legacy plain-string marker
    }

    return {
      completed_at: raw,
      evaluation_id: null,
      legacy: true,
    }
  } catch {
    return null
  }
}

function clearEvaluationCompletedLocally(token) {
  try {
    window.localStorage.removeItem(completionStorageKey(token))
  } catch {
    // ignore storage failures
  }
}

async function verifyCompletedState(token) {
  loading.value = true

  const marker = getCompletionMarker(token)
  if (!marker) {
    await router.replace({ name: 'anonymous-evaluation', params: { token } })
    return
  }

  try {
    const { data } = await publicApi.get(`/public/evaluations/${token}`)

    const criteriaList = Array.isArray(data?.criteria) ? data.criteria : []
    const itemsList = Array.isArray(data?.items) ? data.items : []

    const scoredCriterionIds = new Set(
      itemsList
        .filter((item) => item?.level_id != null && item?.criterion_id != null)
        .map((item) => String(item.criterion_id)),
    )

    const allScoredOnServer = criteriaList.length > 0
      && criteriaList.every((criterion) => scoredCriterionIds.has(String(criterion.id)))

    const markerEvaluationId = marker?.evaluation_id
    const currentEvaluationId = data?.evaluation?.id
    const sameEvaluation = markerEvaluationId == null
      || currentEvaluationId == null
      || String(markerEvaluationId) === String(currentEvaluationId)

    if (!allScoredOnServer || !sameEvaluation) {
      clearEvaluationCompletedLocally(token)
      await router.replace({ name: 'anonymous-evaluation', params: { token } })
      return
    }
  } catch {
    // Если ссылка недействительна/лист закрыт, показываем экран evaluate с его обработкой ошибок.
    await router.replace({ name: 'anonymous-evaluation', params: { token } })
    return
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  verifyCompletedState(props.token)
})

watch(() => props.token, (token) => {
  verifyCompletedState(token)
})
</script>

<template>
  <div v-if="loading" class="mx-auto flex min-h-[70vh] w-full max-w-2xl items-center justify-center px-2">
    <div class="text-sm text-gray-500 dark:text-gray-400">Проверка статуса...</div>
  </div>
  <div v-else class="mx-auto flex min-h-[70vh] w-full max-w-2xl items-center justify-center px-2">
    <div class="w-full rounded-2xl border border-emerald-200/70 bg-gradient-to-br from-white to-emerald-50 p-8 text-center shadow-sm dark:border-emerald-900/50 dark:from-gray-900 dark:to-emerald-950/30">
      <div class="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-7 w-7" viewBox="0 0 20 20" fill="currentColor">
          <path fill-rule="evenodd" d="M16.704 5.29a1 1 0 0 1 .006 1.414l-7.2 7.25a1 1 0 0 1-1.42.003l-3.2-3.2a1 1 0 0 1 1.414-1.414l2.49 2.49 6.493-6.542a1 1 0 0 1 1.417-.001Z" clip-rule="evenodd" />
        </svg>
      </div>
      <h1 class="mb-2 text-2xl font-semibold text-gray-900 dark:text-gray-100">Оценка завершена</h1>
      <p class="mx-auto max-w-xl text-sm leading-relaxed text-gray-600 dark:text-gray-300">
        Вы уже оценили эту работу
      </p>
    </div>
  </div>
</template>
