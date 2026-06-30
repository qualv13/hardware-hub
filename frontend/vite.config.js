import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import http from 'node:http'

// In dev, proxy API calls to the FastAPI backend on :8000.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        // Use 127.0.0.1 (not "localhost") so Node doesn't try IPv6 ::1 first,
        // which uvicorn (bound to 127.0.0.1) isn't listening on.
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // Disable keep-alive: uvicorn closes idle keep-alive sockets, and a
        // reused (now-dead) socket makes the first request after a pause fail
        // with an intermittent ECONNRESET -> HTTP 500. A fresh connection per
        // request avoids that entirely.
        agent: new http.Agent({ keepAlive: false }),
      },
    },
  },
})
