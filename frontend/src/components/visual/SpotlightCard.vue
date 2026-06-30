<script setup>
// Cursor-following spotlight on hover (ported from the React Bits
// "SpotlightCard" idea, MIT).
import { ref } from 'vue'

const el = ref(null)

function move(e) {
  const r = el.value.getBoundingClientRect()
  el.value.style.setProperty('--mx', `${e.clientX - r.left}px`)
  el.value.style.setProperty('--my', `${e.clientY - r.top}px`)
}
</script>

<template>
  <div ref="el" class="spotlight-card" @mousemove="move">
    <div class="spotlight" aria-hidden="true"></div>
    <div class="spotlight-content"><slot /></div>
  </div>
</template>

<style scoped>
.spotlight-card { position: relative; overflow: hidden; }
.spotlight {
  position: absolute; inset: 0; opacity: 0; transition: opacity 0.3s; pointer-events: none;
  background: radial-gradient(220px circle at var(--mx) var(--my), rgba(124, 58, 237, 0.13), transparent 70%);
}
.spotlight-card:hover .spotlight { opacity: 1; }
.spotlight-content { position: relative; z-index: 1; }
</style>
