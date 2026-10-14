<script setup>
import { computed, ref } from 'vue'
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import { assetUrl } from '../../links.js'

const props = defineProps({
  variant: { type: String, default: 'grid' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()
const photos = computed(() => props.content.items.filter((item) => item.image))
const opened = ref(-1)

function open(index) {
  if (!editor) opened.value = index
}
function step(delta) {
  opened.value = (opened.value + delta + photos.value.length) % photos.value.length
}
function keydown(event) {
  if (event.key === 'Escape') opened.value = -1
  if (event.key === 'ArrowRight') step(1)
  if (event.key === 'ArrowLeft') step(-1)
}
</script>

<template>
  <section v-if="photos.length || editor" class="skb-gallery" :class="`skb-gallery--${variant}`">
    <h2 v-if="content.title" class="skb-title">{{ content.title }}</h2>
    <ul v-if="photos.length" class="skb-gallery__list">
      <li v-for="(photo, index) in photos" :key="index">
        <button type="button" class="skb-gallery__thumb" @click="open(index)">
          <img :src="assetUrl(data, photo.image)" :alt="photo.caption || photo.image.alt || ''" loading="lazy" />
        </button>
        <p v-if="photo.caption" class="skb-gallery__caption">{{ photo.caption }}</p>
      </li>
    </ul>
    <SkbEmpty v-else text="Загрузите фотографии в панели настроек справа." />
    <div v-if="opened >= 0" class="skb-lightbox" role="dialog" aria-modal="true" tabindex="-1" @keydown="keydown" @click.self="opened = -1">
      <img :src="assetUrl(data, photos[opened].image)" :alt="photos[opened].caption || ''" class="skb-lightbox__image" />
      <p v-if="photos[opened].caption" class="skb-lightbox__caption">{{ photos[opened].caption }}</p>
      <button type="button" class="skb-lightbox__close" aria-label="Закрыть" @click="opened = -1">×</button>
      <template v-if="photos.length > 1">
        <button type="button" class="skb-lightbox__prev" aria-label="Предыдущее фото" @click="step(-1)">‹</button>
        <button type="button" class="skb-lightbox__next" aria-label="Следующее фото" @click="step(1)">›</button>
      </template>
    </div>
  </section>
</template>
