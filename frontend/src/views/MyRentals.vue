<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import ShinyText from '../components/visual/ShinyText.vue'

const items = ref([])

async function load() {
  const { data } = await api.get('/rentals/mine')
  items.value = data
}

async function returnItem(it) {
  try {
    await api.post(`/hardware/${it.id}/return`)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Could not return')
  }
}

onMounted(load)
</script>

<template>
  <h1 class="page-title"><ShinyText text="My Rentals" /></h1>

  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Device Name</th><th>Brand</th><th>Serial Number</th><th>Status</th><th class="right">Action</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td>{{ it.name }}</td>
          <td>{{ it.brand || '—' }}</td>
          <td class="muted">{{ it.serial_number || '—' }}</td>
          <td><StatusBadge :status="it.status" /></td>
          <td class="right"><button class="btn ghost small" @click="returnItem(it)">Return</button></td>
        </tr>
        <tr v-if="!items.length">
          <td colspan="5" class="empty">You don't have any active rentals</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
