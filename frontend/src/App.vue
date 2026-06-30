<script setup>
import { useRoute } from 'vue-router'
import { computed } from 'vue'
import Sidebar from './components/Sidebar.vue'
import ClickSpark from './components/visual/ClickSpark.vue'

const route = useRoute()
const showShell = computed(() => route.path !== '/login')
</script>

<template>
  <ClickSpark />
  <div v-if="showShell" class="layout">
    <Sidebar />
    <main class="main">
      <router-view />
    </main>
  </div>
  <router-view v-else />
</template>
