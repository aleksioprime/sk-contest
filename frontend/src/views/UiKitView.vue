<script setup>
import { SitePage, createBlockInstance, getBlock } from '@sk-events/blocks'
import { ref } from 'vue'
import UiBadge from '@/components/ui/UiBadge.vue'
import UiButton from '@/components/ui/UiButton.vue'
import UiCard from '@/components/ui/UiCard.vue'
import UiInput from '@/components/ui/UiInput.vue'

const title = ref('')
const accents = ['#534ab7', '#0f6e56', '#993c1d', '#185fa5']
const accent = ref(accents[0])

const hero = createBlockInstance(getBlock('hero'), 'demo-hero')
hero.props.eyebrow = 'VII научно-практическая конференция'
hero.props.title = 'SkolStart 2027'
hero.props.subtitle = 'Ученики 5–11 классов представляют исследовательские и инженерные проекты экспертам.'
const about = createBlockInstance(getBlock('text'), 'demo-text')
about.props.title = 'О конференции'
about.props.body = '<p>Пример блока «Текст». Содержимое редактируется в Tiptap и очищается на сервере.</p>'
about.common.background = 'muted'

const page = { blocks: [hero, about] }
const event = { dates: '12 марта – 18 апреля 2027', place: 'Гимназия Сколково' }
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
        <UiInput v-model="title" label="Название мероприятия" placeholder="SkolStart 2027" hint="Показывается на лендинге и в кабинете" />
        <UiInput label="Адрес лендинга" model-value="skolstart" error="Этот адрес уже занят" />
      </div>
    </UiCard>

    <UiCard>
      <template #title>Блоки лендинга</template>
      <div class="mb-4 flex items-center gap-2 text-sm">
        Цвет темы:
        <button
          v-for="color in accents"
          :key="color"
          type="button"
          class="size-6 rounded-full ring-offset-2"
          :class="{ 'ring-2 ring-ink': color === accent }"
          :style="{ background: color }"
          :aria-label="`Цвет ${color}`"
          @click="accent = color"
        />
      </div>
      <div class="overflow-hidden rounded-card border border-line">
        <SitePage :page="page" :event="event" :theme="{ accent }" />
      </div>
    </UiCard>
  </div>
</template>
