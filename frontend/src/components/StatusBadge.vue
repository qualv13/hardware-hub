<script setup>
import { computed } from 'vue'

const props = defineProps({ status: String })

// Canonical "In Use" is shown as "Rented" to match the wireframe.
const label = computed(() => (props.status === 'In Use' ? 'Rented' : props.status))
const cls = computed(() => {
  switch (props.status) {
    case 'Available': return 'available'
    case 'In Use': return 'in-use'
    case 'Repair': return 'repair'
    default: return 'unknown'
  }
})
</script>

<template>
  <span :class="['badge', cls]">{{ label }}</span>
</template>
