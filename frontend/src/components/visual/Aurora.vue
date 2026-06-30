<script setup>
// Soft animated "aurora" backdrop (ported from the React Bits aurora/gradient
// background idea, MIT) — pure CSS, GPU-friendly, sits behind content.
</script>

<template>
  <div class="aurora" aria-hidden="true">
    <span class="aurora-blob b1"></span>
    <span class="aurora-blob b2"></span>
    <span class="aurora-blob b3"></span>
  </div>
</template>

<style scoped>
.aurora { position: absolute; inset: 0; overflow: hidden; z-index: 0; pointer-events: none; }
.aurora-blob {
  position: absolute; border-radius: 50%; filter: blur(70px);
  opacity: 0.55; mix-blend-mode: multiply; animation: drift 18s ease-in-out infinite;
}
.b1 { width: 460px; height: 460px; background: #c4b5fd; top: -120px; left: -80px; animation-delay: 0s; }
.b2 { width: 420px; height: 420px; background: #99f6e4; bottom: -150px; right: -70px; animation-delay: -6s; }
.b3 { width: 380px; height: 380px; background: #bfdbfe; top: 30%; left: 42%; animation-delay: -12s; }

@keyframes drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(40px, 30px) scale(1.1); }
  66% { transform: translate(-30px, 20px) scale(0.95); }
}
@media (prefers-reduced-motion: reduce) {
  .aurora-blob { animation: none; }
}
</style>
