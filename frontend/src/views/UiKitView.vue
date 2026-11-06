<script setup>
/** Витрина компонентов интерфейса. */
import { ref } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'
import UiSelect from '@/components/ui/UiSelect.vue'

const KIT_TOPICS = ['Биология', 'География', 'Информатика', 'История', 'Литература', 'Математика', 'Физика', 'Химия', 'Экология']
const kitStage = ref(null)
const kitTopics = ref([])

const title = ref('')
</script>

<template>
  <div class="grid gap-8">
    <h1 class="text-2xl font-bold">Компоненты</h1>

    <UiCard>
      <template #title>Кнопки и метки</template>
      <div class="flex flex-wrap items-center gap-3">
        <UiButton variant="primary">Опубликовать</UiButton>
        <UiButton>Сохранить черновик</UiButton>
        <UiButton variant="ghost">Отмена</UiButton>
        <UiButton variant="danger">Удалить</UiButton>
        <UiButton variant="primary" loading>Сохранение</UiButton>
      </div>
      <div class="mt-4 flex flex-wrap gap-2">
        <UiBadge>черновик</UiBadge>
        <UiBadge tone="brand">регистрация</UiBadge>
        <UiBadge tone="success">принята</UiBadge>
        <UiBadge tone="warning">на доработке</UiBadge>
        <UiBadge tone="danger">отклонена</UiBadge>
        <UiBadge tone="score">8,75 балла</UiBadge>
      </div>
    </UiCard>

    <UiCard>
      <template #title>Поля</template>
      <div class="grid max-w-md gap-4">
        <UiInput v-model="title" label="Название мероприятия" placeholder="SkolStart 2027" hint="Показывается на открытой форме и в кабинете" />
        <UiInput label="Адрес формы" model-value="skolstart" error="Этот адрес уже занят" />
        <label class="grid gap-1.5 text-sm font-medium">
          Этап
          <UiSelect v-model="kitStage">
            <option :value="null">Без этапа</option>
            <option value="first">Заочный этап</option>
            <option value="final">Финал</option>
          </UiSelect>
        </label>
        <label class="grid gap-1.5 text-sm font-medium">
          Направления, несколько и с поиском
          <UiSelect v-model="kitTopics" multiple searchable placeholder="Выберите направления">
            <option v-for="topic in KIT_TOPICS" :key="topic" :value="topic">{{ topic }}</option>
          </UiSelect>
        </label>
      </div>
    </UiCard>
  </div>
</template>
