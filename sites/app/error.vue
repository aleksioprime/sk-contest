<script setup>
const props = defineProps({ error: { type: Object, required: true } })
const notFound = props.error.statusCode === 404
useSeoMeta({ title: notFound ? 'Страница не найдена' : 'Ошибка' })
</script>

<template>
  <main class="error">
    <h1>{{ notFound ? 'Такой страницы нет' : 'Что-то пошло не так' }}</h1>
    <p>
      {{ notFound ? 'Возможно, мероприятие ещё не опубликовано или адрес набран с ошибкой.' : 'Попробуйте обновить страницу через минуту.' }}
    </p>
  </main>
</template>

<style scoped>
.error {
  font-family: 'Golos Text', system-ui, sans-serif;
  max-width: 560px;
  margin: 20vh auto;
  padding: 0 20px;
  color: #1d1a2b;
}
</style>
