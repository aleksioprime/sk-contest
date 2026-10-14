<script setup>
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'

defineProps({
  variant: { type: String, default: 'cards' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()
</script>

<template>
  <section v-if="data.directions.length || editor" class="skb-directions" :class="`skb-directions--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <SkbText as="p" class="skb-lead" path="intro" :value="content.intro" placeholder="Вступление (необязательно)" multiline />
    <ul v-if="data.directions.length" class="skb-directions__list">
      <li v-for="direction in data.directions" :key="direction.title" class="skb-directions__item">
        <p class="skb-directions__name">{{ direction.title }}</p>
        <p v-if="variant === 'cards' && direction.description" class="skb-directions__text">{{ direction.description }}</p>
      </li>
    </ul>
    <SkbEmpty v-else text="Направления берутся из настроек мероприятия. Добавьте их на вкладке «Направления»." />
  </section>
</template>
