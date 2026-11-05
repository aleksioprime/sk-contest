<script setup>
/** Витрина компонентов интерфейса. */
import { ref } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'

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
      </div>
    </UiCard>
  </div>
</template>
