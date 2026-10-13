<script setup>
import { computed } from 'vue'
import { blocks } from './registry.js'
import { themeToCssVars } from './theme.js'

const props = defineProps({
  page: { type: Object, required: true },
  theme: { type: Object, default: () => ({}) },
  event: { type: Object, default: () => ({}) },
  phase: { type: String, default: 'always' }, // registration | results | always
})

const visibleBlocks = computed(() =>
  props.page.blocks.filter((item) => {
    if (!blocks[item.type] || item.hidden) return false
    const rule = item.common?.visibility ?? 'always'
    return rule === 'always' || rule === props.phase
  }),
)
const style = computed(() => themeToCssVars(props.theme))
</script>

<template>
  <div class="skb-site" :style="style">
    <div
      v-for="item in visibleBlocks"
      :id="item.common?.anchor || undefined"
      :key="item.id"
      class="skb-section"
      :class="`skb-section--${item.common?.background ?? 'default'}`"
    >
      <component :is="blocks[item.type].component" :variant="item.variant" :props="item.props" :event="event" />
    </div>
  </div>
</template>
