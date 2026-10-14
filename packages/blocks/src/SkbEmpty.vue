<script setup>
/** Подсказка в редакторе, когда блоку нечего показать. На сайте не выводится. */
import { useEditor } from './editing.js'

defineProps({ text: { type: String, required: true } })
const editor = useEditor()
</script>

<template>
  <p v-if="editor" class="skb-empty">{{ text }}</p>
</template>
