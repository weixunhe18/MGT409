import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The API and images are proxied so the browser sees one origin. That keeps the
// httpOnly session cookie first-party: localhost:5190 and 127.0.0.1:8020 count
// as different sites, and a SameSite=Lax cookie is not sent across sites.
const BACKEND = 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': BACKEND,
      '/images': BACKEND,
      // Without this, /motion/*.webm hits the SPA fallback and the browser is
      // handed index.html where it expected a video — which fails silently.
      '/motion': BACKEND,
    },
  },
})
