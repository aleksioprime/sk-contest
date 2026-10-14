<script setup>
import { onMounted, ref } from 'vue'
import { errorMessage } from '@/api/http'
import { fetchVersions, restoreVersion } from '@/api/sites'
import SkeletonList from '@/components/skeleton/SkeletonList.vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'

const props = defineProps({ eventId: { type: [String, Number], required: true } })
const emit = defineEmits(['restored'])
const versions = ref(null)
const error = ref('')
const confirm = ref(null)

async function load() {
  try {
    versions.value = await fetchVersions(props.eventId)
  } catch (e) {
    error.value = errorMessage(e)
    versions.value = []
  }
}

async function restore(version) {
  confirm.value = null
  try {
    emit('restored', await restoreVersion(props.eventId, version.id))
  } catch (e) {
    error.value = errorMessage(e)
  }
}

onMounted(load)
defineExpose({ load })
</script>

<template>
  <div class="grid gap-3 text-sm">
    <p class="text-ink-muted">Каждая публикация сохраняется. Черновик можно вернуть к любой версии, затем опубликовать.</p>
    <p v-if="error" role="alert" class="text-red-700">{{ error }}</p>
    <SkeletonList v-if="!versions" :rows="3" />
    <p v-else-if="!versions.length" class="text-ink-muted">Сайт ещё не публиковался.</p>
    <ul v-else class="grid gap-2">
      <li v-for="v in versions" :key="v.id" class="grid gap-1 rounded-control border border-line p-3">
        <div class="flex items-center gap-2">
          <span class="font-medium">Версия {{ v.number }}</span>
          <UiBadge v-if="v.published" tone="success">На сайте</UiBadge>
        </div>
        <p class="text-ink-muted">
          {{ new Date(v.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) }}<span v-if="v.created_by"> · {{ v.created_by }}</span>
        </p>
        <p v-if="v.note">{{ v.note }}</p>
        <div v-if="confirm === v.id" class="flex flex-wrap items-center gap-2">
          Заменить черновик этой версией?
          <UiButton size="sm" variant="primary" @click="restore(v)">Вернуть</UiButton>
          <UiButton size="sm" variant="ghost" @click="confirm = null">Отмена</UiButton>
        </div>
        <UiButton v-else size="sm" variant="ghost" class="justify-self-start" @click="confirm = v.id">Вернуть в черновик</UiButton>
      </li>
    </ul>
  </div>
</template>
