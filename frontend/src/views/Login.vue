<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import Aurora from '../components/visual/Aurora.vue'
import ShinyText from '../components/visual/ShinyText.vue'

const auth = useAuth()
const router = useRouter()
const localEmail = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  const fullEmail = localEmail.value.trim() + '@booksy.com'
  loading.value = true
  try {
    await auth.login(fullEmail, password.value)
    router.push('/hardware')
  } catch (e) {
    error.value = e.response?.data?.detail || 'Login failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <Aurora />
    <form class="login-card" @submit.prevent="submit">
      <div class="box">📦</div>
      <h1><ShinyText text="Welcome back" /></h1>
      <p class="sub">Sign in to your account</p>

      <label>Email (company domain only)</label>
      <div class="input-group">
        <input
          class="input input-group-field"
          v-model="localEmail"
          type="text"
          placeholder="name"
          autocomplete="username"
        />
        <span class="input-group-suffix">@booksy.com</span>
      </div>

      <label>Password</label>
      <input class="input" v-model="password" type="password" placeholder="Enter your password" autocomplete="current-password" />

      <p v-if="error" class="error">{{ error }}</p>

      <button class="btn primary" style="width:100%; margin-top:22px" :disabled="loading">
        {{ loading ? 'Signing in…' : 'Login' }}
      </button>
    </form>
  </div>
</template>
