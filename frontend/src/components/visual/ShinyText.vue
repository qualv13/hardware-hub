<script setup>
// Animated shimmer sweep over text (ported from the React Bits "ShinyText"
// idea, MIT). Uses background-clip:text so it works on any heading.
defineProps({ text: { type: String, required: true } })
</script>

<template>
  <span class="shiny-text">{{ text }}</span>
</template>

<style scoped>
.shiny-text {
  background: linear-gradient(110deg, var(--text) 35%, #a78bfa 50%, var(--text) 65%);
  background-size: 220% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  animation: shine 5s linear infinite;
}
@keyframes shine { to { background-position: -220% 0; } }
@media (prefers-reduced-motion: reduce) {
  .shiny-text { animation: none; }
}
</style>
