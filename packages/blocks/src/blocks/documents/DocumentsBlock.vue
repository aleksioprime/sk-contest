<script setup>
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'
import { assetUrl } from '../../links.js'

defineProps({
  variant: { type: String, default: 'list' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()

function extension(file) {
  return (file?.name?.split('.').pop() ?? '').toUpperCase().slice(0, 4)
}
</script>

<template>
  <section v-if="content.items.length || editor" class="skb-documents" :class="`skb-documents--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <ul v-if="content.items.length" class="skb-documents__list">
      <li v-for="(doc, index) in content.items" :key="index" class="skb-documents__item">
        <span class="skb-documents__ext" aria-hidden="true">{{ extension(doc.file) || 'DOC' }}</span>
        <div class="skb-documents__body">
          <a v-if="doc.file" :href="assetUrl(data, doc.file)" class="skb-documents__link" target="_blank" rel="noopener">
            {{ doc.title || doc.file.name }}
          </a>
          <SkbText v-else as="p" class="skb-documents__link" :path="`items.${index}.title`" :value="doc.title" placeholder="Название документа" />
          <p v-if="doc.note" class="skb-documents__note">{{ doc.note }}</p>
        </div>
      </li>
    </ul>
    <SkbEmpty v-else text="Загрузите документы в панели настроек справа." />
  </section>
</template>
