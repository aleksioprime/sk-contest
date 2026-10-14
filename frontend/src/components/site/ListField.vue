<script setup>
/** Повторяющиеся элементы блока: добавить, удалить, перетащить, развернуть для правки. */
import { defaultProps } from '@sk-events/blocks'
import { ref } from 'vue'
import PropField from './PropField.vue'

const props = defineProps({ prop: { type: Object, required: true } })
const items = defineModel({ type: Array, default: () => [] })
const open = ref(null)
const dragging = ref(null)

function title(item, index) {
  return (props.prop.itemTitle && item[props.prop.itemTitle]) || `Элемент ${index + 1}`
}

function add() {
  // Новое значение модели придёт от родителя позже, поэтому индекс считаем заранее
  open.value = items.value.length
  items.value = [...items.value, defaultProps(props.prop.item)]
}

function remove(index) {
  items.value = items.value.filter((_, i) => i !== index)
  open.value = null
}

function setField(index, name, value) {
  items.value = items.value.map((item, i) => (i === index ? { ...item, [name]: value } : item))
}

function drop(index) {
  if (dragging.value === null || dragging.value === index) return
  const list = [...items.value]
  const [moved] = list.splice(dragging.value, 1)
  list.splice(index, 0, moved)
  items.value = list
  open.value = null
  dragging.value = null
}
</script>

<template>
  <div class="grid gap-2 text-sm">
    <span class="font-medium">{{ prop.label }}</span>
    <ul class="grid gap-1.5">
      <li
        v-for="(item, index) in items"
        :key="index"
        class="rounded-control border border-line bg-surface"
        :class="{ 'opacity-50': dragging === index }"
        @dragover.prevent
        @drop="drop(index)"
      >
        <div class="flex items-center gap-1 px-2 py-1.5">
          <span
            draggable="true"
            class="cursor-grab px-1 text-ink-muted select-none"
            title="Перетащите, чтобы поменять порядок"
            aria-hidden="true"
            @dragstart="dragging = index"
            @dragend="dragging = null"
          >⋮⋮</span>
          <button type="button" class="min-w-0 flex-1 truncate text-left" @click="open = open === index ? null : index">
            {{ title(item, index) }}
          </button>
          <button type="button" class="rounded px-1.5 text-ink-muted hover:bg-red-50 hover:text-red-700" :aria-label="`Удалить ${title(item, index)}`" @click="remove(index)">×</button>
        </div>
        <div v-if="open === index" class="grid gap-3 border-t border-line p-3">
          <PropField
            v-for="(field, name) in prop.item"
            :key="name"
            :prop="field"
            :model-value="item[name]"
            @update:model-value="setField(index, name, $event)"
          />
        </div>
      </li>
    </ul>
    <button
      v-if="!prop.max || items.length < prop.max"
      type="button"
      class="justify-self-start rounded-control border border-dashed border-line px-3 py-1.5 text-brand-700 hover:bg-brand-50"
      @click="add"
    >
      + Добавить
    </button>
  </div>
</template>
