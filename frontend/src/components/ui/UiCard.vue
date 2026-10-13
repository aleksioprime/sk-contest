<template>
  <section class="rounded-card border border-line bg-surface p-5">
    <header v-if="$slots.title" class="mb-3 text-lg font-semibold"><slot name="title" /></header>
    <slot />
  </section>
</template>
