<script setup>
import { useEditor } from '../../editing.js'
import SkbText from '../../SkbText.vue'

defineProps({
  variant: { type: String, default: 'default' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
// В редакторе все ответы раскрыты, чтобы их можно было править
const editor = useEditor()
</script>

<template>
  <section class="skb-faq">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <details v-for="(item, index) in content.items" :key="index" class="skb-faq__item" :open="!!editor">
      <summary class="skb-faq__question">
        <SkbText as="span" :path="`items.${index}.question`" :value="item.question" placeholder="Вопрос" />
      </summary>
      <SkbText as="p" class="skb-faq__answer" :path="`items.${index}.answer`" :value="item.answer" placeholder="Ответ" multiline />
    </details>
  </section>
</template>
