<script setup>
import { computed, provide } from 'vue'
import { BLOCK_KEY, useEditor } from './editing.js'
import { blocks } from './registry.js'

const props = defineProps({
  item: { type: Object, required: true },
  data: { type: Object, required: true },
})

provide(
  BLOCK_KEY,
  computed(() => props.item.id),
)
const editor = useEditor()
const selected = computed(() => editor?.selectedId === props.item.id)

function click(event) {
  if (!editor) return
  // В редакторе ссылки не уводят со страницы, клик выбирает блок
  if (event.target.closest('a')) event.preventDefault()
  editor.select(props.item.id)
}
</script>

<template>
  <div
    :id="item.common?.anchor || undefined"
    class="skb-section"
    :class="[
      `skb-section--${item.common?.background ?? 'default'}`,
      `skb-section--type-${item.type}`,
      { 'skb-section--editing': editor, 'skb-section--selected': selected },
    ]"
    :data-block-id="item.id"
    @click="click"
  >
    <component :is="blocks[item.type].component" :variant="item.variant" :content="item.props" :data="data" />
  </div>
</template>
