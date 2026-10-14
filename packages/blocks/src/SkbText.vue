<script setup>
/** Текст блока. В редакторе правится прямо на превью, на сайте — обычный тег. */
import { computed } from 'vue'
import { useBlockId, useEditor } from './editing.js'

const props = defineProps({
  as: { type: String, default: 'span' },
  path: { type: String, required: true },
  value: { type: String, default: '' },
  fallback: { type: String, default: '' },
  placeholder: { type: String, default: 'Введите текст' },
  multiline: { type: Boolean, default: false },
})

const editor = useEditor()
const blockId = useBlockId()
const shown = computed(() => props.value || props.fallback)

function commit(event) {
  const text = event.target.innerText.replace(/\n{3,}/g, '\n\n').trim()
  if (text !== props.value) editor.update(blockId.value, props.path, text)
}

function keydown(event) {
  if (event.key === 'Enter' && !props.multiline) {
    event.preventDefault()
    event.target.blur()
  }
  if (event.key === 'Escape') event.target.blur()
}
</script>

<template>
  <component
    :is="as"
    v-if="editor"
    class="skb-editable"
    :class="{ 'skb-editable--fallback': fallback }"
    contenteditable="plaintext-only"
    spellcheck="true"
    :data-placeholder="fallback || placeholder"
    @blur="commit"
    @keydown="keydown"
    v-text="value"
  />
  <component :is="as" v-else-if="shown" :class="{ 'skb-multiline': multiline }">{{ shown }}</component>
</template>
