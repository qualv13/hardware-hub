<script setup>
// Click-spark effect (ported to Vue from the React Bits "ClickSpark" idea, MIT).
// Renders a fixed, click-through canvas and bursts short rays on every click.
import { onMounted, onBeforeUnmount, ref } from 'vue'

const props = defineProps({
  color: { type: String, default: '#7c3aed' },
  count: { type: Number, default: 8 },
  size: { type: Number, default: 12 },
  duration: { type: Number, default: 450 },
})

const canvas = ref(null)
let ctx, raf = null, sparks = [], dpr = 1, w = 0, h = 0

function resize() {
  const c = canvas.value
  if (!c) return
  dpr = window.devicePixelRatio || 1
  w = window.innerWidth
  h = window.innerHeight
  c.width = w * dpr
  c.height = h * dpr
  c.style.width = w + 'px'
  c.style.height = h + 'px'
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
}

function spawn(x, y) {
  const now = performance.now()
  for (let i = 0; i < props.count; i++) {
    sparks.push({ x, y, a: (Math.PI * 2 * i) / props.count, start: now })
  }
  if (!raf) raf = requestAnimationFrame(draw)
}

const easeOut = (t) => 1 - Math.pow(1 - t, 3)

function draw(now) {
  ctx.clearRect(0, 0, w, h)
  sparks = sparks.filter((s) => now - s.start < props.duration)
  ctx.strokeStyle = props.color
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  for (const s of sparks) {
    const t = easeOut((now - s.start) / props.duration)
    const dist = props.size + t * 18
    const len = props.size * (1 - t)
    ctx.globalAlpha = 1 - t
    ctx.beginPath()
    ctx.moveTo(s.x + Math.cos(s.a) * dist, s.y + Math.sin(s.a) * dist)
    ctx.lineTo(s.x + Math.cos(s.a) * (dist + len), s.y + Math.sin(s.a) * (dist + len))
    ctx.stroke()
  }
  ctx.globalAlpha = 1
  raf = sparks.length ? requestAnimationFrame(draw) : null
}

const onClick = (e) => spawn(e.clientX, e.clientY)

onMounted(() => {
  ctx = canvas.value.getContext('2d')
  resize()
  window.addEventListener('resize', resize)
  window.addEventListener('click', onClick)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  window.removeEventListener('click', onClick)
  if (raf) cancelAnimationFrame(raf)
})
</script>

<template>
  <canvas ref="canvas" class="click-spark" aria-hidden="true"></canvas>
</template>

<style>
.click-spark { position: fixed; inset: 0; pointer-events: none; z-index: 9999; }
</style>
