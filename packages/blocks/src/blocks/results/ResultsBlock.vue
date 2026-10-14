<script setup>
import SkbEmpty from '../../SkbEmpty.vue'
import SkbText from '../../SkbText.vue'

defineProps({
  variant: { type: String, default: 'cards' },
  content: { type: Object, required: true },
  data: { type: Object, required: true },
})
const AWARDS = { winner: 'Победитель', prize: 'Призёр' }
</script>

<template>
  <section v-if="data.results.length || data.editing" class="skb-results" :class="`skb-results--${variant}`">
    <SkbText as="h2" class="skb-title" path="title" :value="content.title" />
    <SkbText as="p" class="skb-lead" path="intro" :value="content.intro" placeholder="Вступление (необязательно)" multiline />
    <div v-for="group in data.results" :key="group.direction" class="skb-results__group">
      <h3 v-if="group.direction" class="skb-subtitle">{{ group.direction }}</h3>
      <table v-if="variant === 'table'" class="skb-table">
        <thead>
          <tr><th>Место</th><th>Работа</th><th>Участники</th></tr>
        </thead>
        <tbody>
          <tr v-for="winner in group.winners" :key="`${winner.rank}-${winner.title}`">
            <td>{{ winner.rank }} · {{ AWARDS[winner.award] }}</td>
            <td>{{ winner.title }}</td>
            <td>{{ winner.participants.join(', ') }}</td>
          </tr>
        </tbody>
      </table>
      <ul v-else class="skb-results__cards">
        <li v-for="winner in group.winners" :key="`${winner.rank}-${winner.title}`" class="skb-results__card" :class="`skb-results__card--${winner.award}`">
          <p class="skb-results__place">{{ winner.rank }} место · {{ AWARDS[winner.award] }}</p>
          <p class="skb-results__work">{{ winner.title }}</p>
          <p class="skb-results__names">{{ winner.participants.join(', ') }}</p>
        </li>
      </ul>
    </div>
    <SkbEmpty v-if="!data.results.length" text="Блок появится на сайте, когда итоги будут опубликованы." />
  </section>
</template>
