import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach the JWT to every request.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config

    // Retry transient CONNECTION failures (no HTTP response received): the dev
    // proxy occasionally can't reach uvicorn on localhost (ECONNREFUSED /
    // ETIMEDOUT / ECONNRESET). Since the request never reached the backend,
    // retrying is safe even for POSTs (no risk of double-applying).
    if (cfg && !err.response) {
      cfg.__retryCount = (cfg.__retryCount || 0) + 1
      if (cfg.__retryCount <= 3) {
        await new Promise((res) => setTimeout(res, 300 * cfg.__retryCount))
        return api(cfg)
      }
    }

    // On auth failure, drop the session and bounce to login.
    if (err.response && err.response.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (location.pathname !== '/login') location.assign('/login')
    }
    return Promise.reject(err)
  }
)

export default api
