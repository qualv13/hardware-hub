<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import ShinyText from '../components/visual/ShinyText.vue'
import CountUp from '../components/visual/CountUp.vue'
import SpotlightCard from '../components/visual/SpotlightCard.vue'

const items = ref([])
const allItems = ref([])
const query = ref('')
const searching = ref(false)
const aiActive = ref(false)

const stats = computed(() => {
  const a = allItems.value
  return {
    total: a.length,
    available: a.filter((i) => i.status === 'Available').length,
    inUse: a.filter((i) => i.status === 'In Use').length,
    repair: a.filter((i) => i.status === 'Repair').length,
  }
})

async function load() {
  aiActive.value = false
  const { data } = await api.get('/hardware', { params: { sort: 'name' } })
  items.value = data
  allItems.value = data
}

async function runSearch() {
  if (!query.value.trim()) return load()
  searching.value = true
  try {
    const { data } = await api.post('/ai/search', { query: query.value })
    items.value = data
    aiActive.value = true
  } finally {
    searching.value = false
  }
}

async function rent(it) {
  try {
    await api.post(`/hardware/${it.id}/rent`)
    await load()
    if (aiActive.value) await runSearch()
  } catch (e) {
    alert(e.response?.data?.detail || 'Could not rent')
  }
}

onMounted(load)
</script>

<template>
  <h1 class="page-title"><ShinyText text="Hardware List" /></h1>

  <div class="stats">
    <SpotlightCard class="card stat">
      <div class="stat-num"><CountUp :value="stats.total" /></div>
      <div class="stat-label">Total devices</div>
    </SpotlightCard>
    <SpotlightCard class="card stat">
      <div class="stat-num"><CountUp :value="stats.available" /></div>
      <div class="stat-label">Available</div>
    </SpotlightCard>
    <SpotlightCard class="card stat">
      <div class="stat-num"><CountUp :value="stats.inUse" /></div>
      <div class="stat-label">Rented</div>
    </SpotlightCard>
    <SpotlightCard class="card stat">
      <div class="stat-num"><CountUp :value="stats.repair" /></div>
      <div class="stat-label">In repair</div>
    </SpotlightCard>
  </div>

  <div class="search">
    <span>🔍</span>
    <input
      v-model="query"
      placeholder="Ask AI… e.g. 'something to test a mobile app on'"
      @keyup.enter="runSearch"
    />
    <span class="spark" @click="runSearch" title="Semantic search">✦</span>
  </div>

  <p v-if="aiActive" class="muted" style="margin:-6px 0 14px">
    AI results for “{{ query }}” · <a href="#" @click.prevent="load">clear</a>
  </p>

  <div class="card">
    <table>
      <thead>
        <tr>
          <th>Device Name</th><th>Brand</th><th>Date Added</th><th>Status</th><th class="right">Action</th>
        </tr>
      </thead>
      <TransitionGroup name="rowfade" tag="tbody">
        <tr v-for="(it, idx) in items" :key="it.id" :style="{ transitionDelay: idx * 30 + 'ms' }">
          <td>{{ it.name }}</td>
          <td>{{ it.brand || '—' }}</td>
          <td>{{ it.purchase_date || '—' }}</td>
          <td><StatusBadge :status="it.status" /></td>
          <td class="right">
            <button class="btn primary small" :disabled="it.status !== 'Available'" @click="rent(it)">Rent</button>
          </td>
        </tr>
        <tr v-if="!items.length" key="empty"><td colspan="5" class="empty">No hardware found.</td></tr>
      </TransitionGroup>
    </table>
  </div>
</template>
