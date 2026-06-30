<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import StatusBadge from '../components/StatusBadge.vue'
import ShinyText from '../components/visual/ShinyText.vue'

const items = ref([])
const showDevice = ref(false)
const showUser = ref(false)
const audit = ref(null)
const auditing = ref(false)
const applyingId = ref(null)
const promptDrafts = ref({})
const results = ref({})
const showHistory = ref(false)
const historyRows = ref([])

const form = ref({ name: '', serial_number: '', brand: '', category: '' })
const userForm = ref({ localEmail: '', name: '', password: '', is_admin: false })

const CATEGORIES = ['Laptop', 'Phone', 'Tablet', 'Monitor', 'Peripheral', 'Audio', 'Other']

async function load() {
  const { data } = await api.get('/hardware', { params: { include_quarantined: true, sort: 'name' } })
  items.value = data
}

async function addDevice() {
  await api.post('/admin/hardware', form.value)
  showDevice.value = false
  form.value = { name: '', serial_number: '', brand: '', category: '' }
  await load()
}

async function addUser() {
  const fullEmail = userForm.value.localEmail.trim() + '@booksy.com'
  try {
    await api.post('/admin/users', {
      email: fullEmail,
      name: userForm.value.name,
      password: userForm.value.password,
      is_admin: userForm.value.is_admin,
    })
    showUser.value = false
    userForm.value = { localEmail: '', name: '', password: '', is_admin: false }
    alert('User created')
  } catch (e) {
    alert(e.response?.data?.detail || 'Could not create user')
  }
}

async function toggleRepair(it) {
  try {
    await api.patch(`/admin/hardware/${it.id}/repair`)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Could not toggle repair status')
    await load()
  }
}

async function remove(it) {
  if (!confirm(`Delete "${it.name}"?`)) return
  try {
    await api.delete(`/admin/hardware/${it.id}`)
    await load()
  } catch (e) {
    alert(e.response?.data?.detail || 'Could not delete device')
  }
}

async function runAudit() {
  auditing.value = true
  try {
    const { data } = await api.get('/ai/audit')
    audit.value = data.issues
    promptDrafts.value = {} // prompts are transient per request
  } catch (e) {
    alert('Audit failed: ' + (e.response?.data?.detail || e.message || 'backend unreachable'))
  } finally {
    auditing.value = false
  }
}

async function fixItem(iss) {
  applyingId.value = iss.id
  try {
    const { data } = await api.post(`/admin/audit/fix/${iss.id}`, {
      prompt: promptDrafts.value[iss.id] || '',
    })
    // Record the outcome of the fix itself BEFORE refreshing, so a transient
    // refresh error can never mask a fix that actually succeeded.
    results.value = {
      ...results.value,
      [iss.id]: data.changes.length
        ? `✓ ${data.changes.join(', ')}`
        : 'ℹ ' + (data.explanation || 'No change applied'),
    }
  } catch (e) {
    results.value = {
      ...results.value,
      [iss.id]: '⚠ ' + (e.response?.data?.detail || e.message || 'Could not apply fix'),
    }
    applyingId.value = null
    return
  }
  // Best-effort refresh; failures here must not overwrite the success message.
  try {
    await runAudit()
    await load()
    if (showHistory.value) await loadHistory()
  } catch (_) {
    /* ignore — the fix already succeeded */
  } finally {
    applyingId.value = null
  }
}

async function loadHistory() {
  const { data } = await api.get('/admin/history')
  historyRows.value = data.history
}

async function toggleHistory() {
  showHistory.value = !showHistory.value
  if (showHistory.value) await loadHistory()
}

const fmt = (iso) => (iso ? iso.slice(0, 16).replace('T', ' ') : '')

onMounted(load)
</script>

<template>
  <div class="row-between">
    <h1 class="page-title"><ShinyText text="Hardware Management" /></h1>
    <div style="display:flex; gap:10px">
      <button class="btn ghost" @click="runAudit" :disabled="auditing">
        {{ auditing ? 'Auditing…' : '✦ AI Audit' }}
      </button>
      <button class="btn ghost" @click="toggleHistory">
        {{ showHistory ? 'Hide History' : '🕑 History' }}
      </button>
      <button class="btn ghost" @click="showUser = true">+ Add User</button>
      <button class="btn primary" @click="showDevice = true">+ Add New Device</button>
    </div>
  </div>

  <!-- History panel -->
  <div v-if="showHistory" class="card audit">
    <div class="audit-item" v-if="!historyRows.length"><b>No fixes recorded yet.</b></div>
    <div class="audit-item history-row" v-for="(h, i) in historyRows" :key="i">
      <span class="muted">{{ fmt(h.at) }}</span>
      <b>#{{ h.hardware_id }} — {{ h.name }}</b>
      <em v-if="h.prompt">“{{ h.prompt }}”</em><em v-else class="muted">(no prompt)</em>
      <span class="hist-arrow">→</span> <span>{{ h.summary }}</span>
    </div>
  </div>

  <!-- AI Inventory Auditor results -->
  <div v-if="audit" class="card audit">
    <div class="audit-item" v-if="!audit.length"><b>No issues found ✅</b></div>
    <div class="audit-item" v-for="iss in audit" :key="iss.id">
      <b>#{{ iss.id }} — {{ iss.name }}</b>
      <span class="tag" v-for="(t, i) in iss.issues" :key="i">{{ t }}</span>
      <div class="audit-review">
        <textarea
          class="input audit-note"
          rows="2"
          v-model="promptDrafts[iss.id]"
          placeholder="Ask the AI to fix this… e.g. 'set the date to 2024-01-15', 'correct the brand', 'move to repair'"
        ></textarea>
        <button
          class="btn primary btn-small"
          :disabled="applyingId === iss.id"
          @click="fixItem(iss)"
        >
          {{ applyingId === iss.id ? 'Asking AI…' : '✦ Ask AI to fix' }}
        </button>
      </div>
      <div v-if="results[iss.id]" class="audit-result">{{ results[iss.id] }}</div>
      <div v-if="iss.history && iss.history.length" class="audit-hist">
        <div class="audit-hist-title">History</div>
        <div v-for="(h, i) in iss.history" :key="i" class="audit-hist-row">
          <span class="muted">{{ fmt(h.at) }}</span>
          <em v-if="h.prompt">“{{ h.prompt }}”</em><em v-else class="muted">(auto)</em>
          <span class="hist-arrow">→</span> {{ h.summary }}
        </div>
      </div>
    </div>
  </div>

  <div class="card" style="margin-top:16px">
    <table>
      <thead>
        <tr>
          <th>Device Name</th><th>Brand</th><th>Serial Number</th><th>Date Added</th><th>Status</th><th class="right">Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="it in items" :key="it.id">
          <td>{{ it.name }}</td>
          <td>{{ it.brand || '—' }}</td>
          <td class="muted">{{ it.serial_number || '—' }}</td>
          <td>{{ it.purchase_date || '—' }}</td>
          <td><StatusBadge :status="it.status" /></td>
          <td class="right">
            <button class="icon-btn" title="Toggle repair" @click="toggleRepair(it)" :disabled="it.quarantined">🔧</button>
            <button class="icon-btn danger" title="Delete" @click="remove(it)">🗑</button>
          </td>
        </tr>
      </tbody>
    </table>
  </div>

  <!-- Add Device modal -->
  <div v-if="showDevice" class="overlay" @click.self="showDevice = false">
    <div class="modal">
      <h2>Add New Device</h2>
      <p class="muted">Enter the details of the new hardware device</p>
      <label>Name</label>
      <input class="input" v-model="form.name" placeholder="e.g. MacBook Pro 16" />
      <label>Serial Number</label>
      <input class="input" v-model="form.serial_number" placeholder="e.g. MBP-2024-001" />
      <label>Brand</label>
      <input class="input" v-model="form.brand" placeholder="e.g. Apple" />
      <label>Category</label>
      <select class="input" v-model="form.category">
        <option value="">Select a category</option>
        <option v-for="c in CATEGORIES" :key="c" :value="c">{{ c }}</option>
      </select>
      <div class="actions">
        <button class="btn ghost" @click="showDevice = false">Cancel</button>
        <button class="btn primary" :disabled="!form.name" @click="addDevice">Add Device</button>
      </div>
    </div>
  </div>

  <!-- Add User modal (spec: accounts are created only by the admin) -->
  <div v-if="showUser" class="overlay" @click.self="showUser = false">
    <div class="modal">
      <h2>Create Account</h2>
      <p class="muted">New users can only be created here.</p>
      <label>Email</label>
      <div class="input-group">
        <input class="input input-group-field" v-model="userForm.localEmail" placeholder="name" autocomplete="off" />
        <span class="input-group-suffix">@booksy.com</span>
      </div>
      <label>Name</label>
      <input class="input" v-model="userForm.name" placeholder="Full name" />
      <label>Password</label>
      <input class="input" v-model="userForm.password" type="password" placeholder="Temporary password" />
      <label style="display:flex; align-items:center; gap:8px; margin-top:14px">
        <input type="checkbox" v-model="userForm.is_admin" style="width:auto" /> Admin
      </label>
      <div class="actions">
        <button class="btn ghost" @click="showUser = false">Cancel</button>
        <button class="btn primary" :disabled="!userForm.localEmail || !userForm.password" @click="addUser">Create</button>
      </div>
    </div>
  </div>
</template>
