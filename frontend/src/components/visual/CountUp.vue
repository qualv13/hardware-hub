<script setup>
// Animated number count-up (ported from the React Bits "CountUp" idea, MIT).
import { ref, onMounted, watch } from 'vue'

const props = defineProps({
  value: { type: Number, default: 0 },
  duration: { type: Number, default: 900 },
})

const display = ref(0)

function run(to) {
  const start = performance.now()
  function step(now) {
    const t = Math.min(1, (now - start) / props.duration)
    const eased = 1 - Math.pow(1 - t, 3)
    display.value = Math.round(to * eased)
    if (t < 1) requestAnimationFrame(step)
  }
  requestAnimationFrame(step)
}

onMounted(() => run(props.value))
watch(() => props.value, (v) => run(v))
</script>

<template>
  <span>{{ display }}</span>
</template>
