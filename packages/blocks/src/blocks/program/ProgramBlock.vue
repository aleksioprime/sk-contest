<script setup>
import { computed, ref } from 'vue'
import { useEditor } from '../../editing.js'
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'
import { dayKey, formatDay, formatTime } from '../../format.js'

const props = defineProps({
  variant: { type: String, default: 'tabs' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const editor = useEditor()

/** Дни → пункты. Для слотов из этапов день и время считаются по Москве. */
const days = computed(() => {
  const map = new Map()
  const push = (day, item) => {
    if (!map.has(day)) map.set(day, [])
    map.get(day).push(item)
  }
  if (props.content.source === 'manual') {
    props.content.items.forEach((item, index) => push(item.day || 'Программа', { ...item, path: `items.${index}` }))
  } else {
    for (const slot of props.data.program) {
      const time = [formatTime(slot.starts_at), formatTime(slot.ends_at)].filter(Boolean).join('–')
      push(formatDay(dayKey(slot.starts_at)), {
        time,
        title: [slot.stage, slot.title].filter(Boolean).join(' · '),
        place: slot.room ? `ауд. ${slot.room}` : '',
        works: props.content.showWorks ? slot.works : [],
      })
    }
  }
  return [...map.entries()].map(([day, items]) => ({ day, items }))
})
const active = ref(0)
const shown = computed(() => (props.variant === 'tabs' ? days.value.slice(active.value, active.value + 1) : days.value))
</script>

<template>
  <section v-if="days.length || editor" class="skb-program" :class="`skb-program--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <div v-if="variant === 'tabs' && days.length > 1" class="skb-tabs" role="tablist">
      <button
        v-for="(day, index) in days"
        :key="day.day"
        type="button"
        role="tab"
        class="skb-tab"
        :aria-selected="active === index"
        @click.stop="active = index"
      >
        {{ day.day }}
      </button>
    </div>
    <div v-for="day in shown" :key="day.day" class="skb-program__day">
      <h3 v-if="variant === 'list' || days.length === 1" class="skb-subtitle">{{ day.day }}</h3>
      <ul class="skb-program__list">
        <li v-for="(item, index) in day.items" :key="index" class="skb-program__item">
          <template v-if="item.path">
            <SkbText as="p" class="skb-program__time" :path="`${item.path}.time`" :value="item.time" placeholder="10:00" />
            <div>
              <SkbText as="p" class="skb-program__title" :path="`${item.path}.title`" :value="item.title" placeholder="Что происходит" />
              <SkbText as="p" class="skb-program__place" :path="`${item.path}.place`" :value="item.place" placeholder="Где" />
            </div>
          </template>
          <template v-else>
            <p class="skb-program__time">{{ item.time }}</p>
            <div>
              <p class="skb-program__title">{{ item.title }}</p>
              <p v-if="item.place" class="skb-program__place">{{ item.place }}</p>
              <ol v-if="item.works?.length" class="skb-program__works">
                <li v-for="work in item.works" :key="work.number">№{{ work.number }} · {{ work.title }}</li>
              </ol>
            </div>
          </template>
        </li>
      </ul>
    </div>
    <SkbEmpty v-if="!days.length" text="Программа появится, когда на вкладке «Ход по этапам» будут слоты защит. Или выберите «Вручную»." />
  </section>
</template>
