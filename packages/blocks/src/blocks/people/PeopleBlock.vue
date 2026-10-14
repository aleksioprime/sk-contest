<script setup>
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'
import { assetUrl } from '../../links.js'

defineProps({
  variant: { type: String, default: 'grid' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()
</script>

<template>
  <section v-if="content.items.length || editor" class="skb-people" :class="`skb-people--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <ul v-if="content.items.length" class="skb-people__list">
      <li v-for="(person, index) in content.items" :key="index" class="skb-people__item">
        <img v-if="variant === 'grid' && person.photo" :src="assetUrl(data, person.photo)" :alt="person.name" class="skb-people__photo" />
        <div v-else-if="variant === 'grid'" class="skb-people__photo skb-people__photo--empty" aria-hidden="true">
          {{ (person.name || '?').slice(0, 1) }}
        </div>
        <div>
          <SkbText as="p" class="skb-people__name" :path="`items.${index}.name`" :value="person.name" placeholder="Имя" />
          <SkbText as="p" class="skb-people__role" :path="`items.${index}.role`" :value="person.role" placeholder="Роль" />
          <SkbText as="p" class="skb-people__text" :path="`items.${index}.text`" :value="person.text" placeholder="О человеке" multiline />
        </div>
      </li>
    </ul>
    <SkbEmpty v-else text="Добавьте людей в панели настроек справа." />
  </section>
</template>
