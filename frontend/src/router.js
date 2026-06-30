import { createRouter, createWebHistory } from 'vue-router'
import { useAuth } from './stores/auth'

import Login from './views/Login.vue'
import HardwareList from './views/HardwareList.vue'
import MyRentals from './views/MyRentals.vue'
import AdminPanel from './views/AdminPanel.vue'

const routes = [
  { path: '/login', component: Login },
  { path: '/', redirect: '/hardware' },
  { path: '/hardware', component: HardwareList, meta: { requiresAuth: true } },
  { path: '/rentals', component: MyRentals, meta: { requiresAuth: true } },
  { path: '/admin', component: AdminPanel, meta: { requiresAuth: true, requiresAdmin: true } },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach((to) => {
  const auth = useAuth()
  if (to.meta.requiresAuth && !auth.isLoggedIn) return '/login'
  if (to.meta.requiresAdmin && !auth.isAdmin) return '/hardware'
  if (to.path === '/login' && auth.isLoggedIn) return '/hardware'
})

export default router
