<script setup>
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <span class="box">📦</span>
      <span>Hardware Manager</span>
    </div>

    <router-link to="/hardware" class="nav-item"><span class="ico">▤</span> Hardware List</router-link>
    <router-link to="/rentals" class="nav-item"><span class="ico">◷</span> My Rentals</router-link>
    <router-link v-if="auth.isAdmin" to="/admin" class="nav-item"><span class="ico">⚙</span> Admin Panel</router-link>

    <div class="spacer" />
    <div class="nav-item" @click="logout"><span class="ico">⏻</span> Logout</div>
  </aside>
</template>
