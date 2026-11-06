<script setup>
import { computed, nextTick, onBeforeUnmount, ref, useId, useSlots, watch } from 'vue'

// Выпадающий список. Варианты задаются обычными <option> в слоте, значения сохраняют свой тип:
//   <UiSelect v-model="stageId"><option :value="null">Без этапа</option>…</UiSelect>
// multiple — выбор нескольких, v-model содержит массив. Поиск включается сам, если вариантов больше SEARCH_FROM;
// searchable или :searchable="false" задают его явно.
defineOptions({ inheritAttrs: false })

const props = defineProps({
  disabled: { type: Boolean, default: false },
  invalid: { type: Boolean, default: false },
  multiple: { type: Boolean, default: false },
  searchable: { type: Boolean, default: undefined },
  placeholder: { type: String, default: 'Не выбрано' },
  size: { type: String, default: 'lg' }, // lg — 40px, md — 36px, sm — 32px
})
const model = defineModel({ type: null })

const SIZES = { lg: 'h-10 px-3', md: 'h-9 px-2.5 text-sm', sm: 'h-8 px-2 text-sm' }
const GAP = 4
const MAX_HEIGHT = 320
const SEARCH_FROM = 8

const slots = useSlots()
const id = useId()
const trigger = ref(null)
const popup = ref(null)
const list = ref(null)
const searchInput = ref(null)
const open = ref(false)
const active = ref(-1)
const query = ref('')
const position = ref({})
let typed = ''
let typedAt = 0

function collect(nodes, into = []) {
  for (const node of nodes) {
    if (node.type === 'option') {
      const text = Array.isArray(node.children) ? node.children.map((c) => c.children ?? '').join('') : node.children
      into.push({
        value: node.props?.value,
        label: String(text ?? '').trim(),
        disabled: node.props?.disabled != null && node.props.disabled !== false,
      })
    } else if (Array.isArray(node.children)) {
      collect(node.children, into)
    }
  }
  return into
}

// Слот читается только при отрисовке: в нём могут быть переменные родительского v-for.
// Первым его читает скрытый блок ширины, остальная разметка и обработчики берут готовый список.
let options = []
function readOptions() {
  options = collect(slots.default?.() ?? [])
  return options
}

function same(a, b) {
  return String(a ?? null) === String(b ?? null)
}
function isSelected(option) {
  return props.multiple ? (model.value ?? []).some((value) => same(value, option.value)) : same(option.value, model.value)
}
function hasSearch() {
  return props.searchable ?? options.length > SEARCH_FROM
}
function visible() {
  const text = query.value.trim().toLowerCase()
  return text ? options.filter((option) => option.label.toLowerCase().includes(text)) : options
}
function triggerLabel() {
  return options.filter(isSelected).map((option) => option.label).join(', ')
}
function isPlaceholder() {
  if (props.multiple) return !(model.value ?? []).length
  return model.value === null || model.value === undefined || model.value === ''
}

function place() {
  if (!trigger.value) return
  const rect = trigger.value.getBoundingClientRect()
  const below = window.innerHeight - rect.bottom - GAP * 2
  const above = rect.top - GAP * 2
  const needed = Math.min(MAX_HEIGHT, popup.value?.scrollHeight ?? MAX_HEIGHT)
  const up = below < needed && above > below
  position.value = {
    left: `${Math.max(GAP, Math.min(rect.left, window.innerWidth - rect.width - GAP))}px`,
    minWidth: `${rect.width}px`,
    maxWidth: `${window.innerWidth - GAP * 2}px`,
    maxHeight: `${Math.min(MAX_HEIGHT, up ? above : below)}px`,
    ...(up ? { bottom: `${window.innerHeight - rect.top + GAP}px` } : { top: `${rect.bottom + GAP}px` }),
  }
}

async function show(seed = '') {
  if (props.disabled || open.value) return
  query.value = seed
  active.value = visible().findIndex(isSelected)
  open.value = true
  place()
  await nextTick()
  place()
  searchInput.value?.focus({ preventScroll: true })
  scrollToActive()
}
function hide(refocus = false) {
  open.value = false
  if (refocus) trigger.value?.focus()
}
function toggle() {
  open.value ? hide(true) : show()
}

function choose(option) {
  if (option.disabled) return
  if (props.multiple) {
    const current = model.value ?? []
    model.value = isSelected(option) ? current.filter((value) => !same(value, option.value)) : [...current, option.value]
    return
  }
  if (!same(option.value, model.value)) model.value = option.value
  hide(true)
}

function scrollToActive() {
  list.value?.children[active.value]?.scrollIntoView?.({ block: 'nearest' })
}
function move(from, step) {
  const items = visible()
  for (let i = from; i >= 0 && i < items.length; i += step) {
    if (!items[i].disabled) {
      active.value = i
      nextTick(scrollToActive)
      return
    }
  }
}

// Быстрый переход по первым буквам, когда поля поиска нет
function typeAhead(char) {
  const now = Date.now()
  typed = now - typedAt > 700 ? char : typed + char
  typedAt = now
  const text = typed.toLowerCase()
  const found = options.findIndex((option) => !option.disabled && option.label.toLowerCase().startsWith(text))
  if (found === -1) return
  if (open.value) {
    active.value = found
    nextTick(scrollToActive)
  } else if (!props.multiple) {
    choose(options[found])
  }
}

function onKeydown(event) {
  const { key } = event
  const inSearch = event.target === searchInput.value
  if (key === 'Tab') {
    if (inSearch) {
      event.preventDefault()
      hide(true)
    } else {
      hide()
    }
    return
  }
  if (key === 'Escape') {
    if (open.value) {
      event.preventDefault()
      event.stopPropagation()
      hide(true)
    }
    return
  }
  if (key === 'ArrowDown' || key === 'ArrowUp' || (!inSearch && (key === 'Home' || key === 'End'))) {
    event.preventDefault()
    if (!open.value) return show()
    const last = visible().length - 1
    if (key === 'ArrowDown') move(active.value + 1, 1)
    if (key === 'ArrowUp') move(active.value === -1 ? last : active.value - 1, -1)
    if (key === 'Home') move(0, 1)
    if (key === 'End') move(last, -1)
    return
  }
  if (key === 'Enter' || (key === ' ' && !inSearch)) {
    event.preventDefault()
    if (!open.value) return show()
    const option = visible()[active.value]
    if (option) choose(option)
    return
  }
  if (!inSearch && key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
    if (hasSearch()) {
      event.preventDefault()
      show(key)
    } else {
      typeAhead(key)
    }
  }
}

function onPointerDown(event) {
  if (!trigger.value?.contains(event.target) && !popup.value?.contains(event.target)) hide()
}
function onScroll(event) {
  if (!popup.value?.contains(event.target)) hide()
}
function listen(on) {
  const method = on ? 'addEventListener' : 'removeEventListener'
  document[method]('pointerdown', onPointerDown, true)
  window[method]('scroll', onScroll, true)
  window[method]('resize', place)
}
watch(open, listen)
watch(query, () => {
  active.value = visible().findIndex((option) => !option.disabled)
  nextTick(place)
})
onBeforeUnmount(() => listen(false))

const activeId = computed(() => (open.value && active.value >= 0 ? `${id}-${active.value}` : undefined))
</script>

<template>
  <button
    ref="trigger"
    type="button"
    role="combobox"
    aria-haspopup="listbox"
    :aria-expanded="open"
    :aria-controls="open ? `${id}-list` : undefined"
    :aria-activedescendant="activeId"
    :aria-invalid="invalid || undefined"
    :disabled="disabled"
    v-bind="$attrs"
    class="inline-flex max-w-full min-w-0 items-center gap-2 rounded-control border bg-surface text-left outline-none transition-colors focus:border-brand-500 disabled:opacity-60"
    :class="[SIZES[size], invalid ? 'border-red-500' : open ? 'border-brand-500' : 'border-line', disabled || invalid ? '' : 'hover:border-brand-200']"
    @click="toggle"
    @keydown="onKeydown"
  >
    <span class="grid min-w-0 flex-1">
      <!-- Скрытые подписи держат ширину по самому длинному варианту, как у обычного select -->
      <span v-for="(option, i) in readOptions()" :key="i" class="invisible col-start-1 row-start-1 truncate" aria-hidden="true">{{ option.label }}</span>
      <span class="col-start-1 row-start-1 truncate" :class="{ 'text-ink-muted': isPlaceholder() }">{{ triggerLabel() || (multiple ? placeholder : '') }}&#8203;</span>
    </span>
    <svg
      class="size-4 shrink-0 text-ink-muted transition-transform"
      :class="{ 'rotate-180': open }"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <path d="m4 6 4 4 4-4" />
    </svg>
  </button>

  <Teleport to="body">
    <div
      v-if="open"
      ref="popup"
      class="fixed z-50 flex flex-col overflow-hidden rounded-control border border-line bg-surface text-sm text-ink shadow-lg"
      :style="position"
    >
      <div v-if="hasSearch()" class="border-b border-line p-1.5">
        <input
          ref="searchInput"
          v-model="query"
          type="search"
          placeholder="Найти…"
          aria-label="Найти в списке"
          :aria-controls="`${id}-list`"
          :aria-activedescendant="activeId"
          class="h-8 w-full rounded-[7px] border border-line bg-surface px-2 text-sm"
          @keydown="onKeydown"
        />
      </div>
      <ul :id="`${id}-list`" ref="list" role="listbox" :aria-multiselectable="multiple || undefined" class="grid min-h-0 flex-1 content-start overflow-y-auto p-1" @mousedown.prevent>
        <li
          v-for="(option, i) in visible()"
          :id="`${id}-${i}`"
          :key="i"
          role="option"
          :aria-selected="isSelected(option)"
          :aria-disabled="option.disabled || undefined"
          class="flex min-h-9 items-center gap-2.5 rounded-[7px] px-2.5 py-1.5"
          :class="[
            option.disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer',
            i === active && !option.disabled ? 'bg-brand-50' : '',
            isSelected(option) && !multiple ? 'font-medium text-brand-700' : '',
          ]"
          @mousemove="active = i"
          @click="choose(option)"
        >
          <span
            v-if="multiple"
            class="flex size-4 shrink-0 items-center justify-center rounded border transition-colors"
            :class="isSelected(option) ? 'border-brand-600 bg-brand-600 text-white' : 'border-ink-muted/50 bg-surface text-transparent'"
            aria-hidden="true"
          >
            <svg class="size-3" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="m3.5 8.5 3 3 6-7" /></svg>
          </span>
          <span class="min-w-0 flex-1 break-words">{{ option.label }}</span>
          <svg v-if="isSelected(option) && !multiple" class="size-4 shrink-0" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="m3.5 8.5 3 3 6-7" />
          </svg>
        </li>
        <li v-if="!visible().length" class="px-2.5 py-1.5 text-ink-muted">{{ query ? 'Ничего не найдено' : 'Нет вариантов' }}</li>
      </ul>
    </div>
  </Teleport>
</template>
