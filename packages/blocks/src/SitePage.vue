<script setup>
import { computed } from 'vue'
import SkbBlockFrame from './SkbBlockFrame.vue'
import { blocks } from './registry.js'
import { themeToCssVars } from './theme.js'

const props = defineProps({
  page: { type: Object, required: true },
  theme: { type: Object, default: () => ({}) },
  data: { type: Object, default: () => ({}) },
  phase: { type: String, default: 'always' }, // registration | results | always
})

const visibleBlocks = computed(() =>
  props.page.blocks.filter((item) => {
    if (!blocks[item.type] || item.hidden) return false
    const rule = item.common?.visibility ?? 'always'
    return rule === 'always' || rule === props.phase
  }),
)
const menu = computed(() =>
  visibleBlocks.value
    .filter((item) => item.common?.anchor && item.common?.menuTitle && !blocks[item.type].isEmpty(item.props, baseData.value))
    .map((item) => ({ anchor: item.common.anchor, title: item.common.menuTitle })),
)
const baseData = computed(() => ({
  event: {},
  registration: {},
  stages: [],
  directions: [],
  results: [],
  program: [],
  stats: {},
  ...props.data,
}))
const blockData = computed(() => ({ ...baseData.value, menu: menu.value }))
const style = computed(() => themeToCssVars(props.theme))
</script>

<template>
  <div class="skb-site" :class="{ 'skb-site--dark': theme?.mode === 'dark' }" :style="style">
    <SkbBlockFrame v-for="item in visibleBlocks" :key="item.id" :item="item" :data="blockData" />
  </div>
</template>
