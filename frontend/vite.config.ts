import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/contracts': 'http://127.0.0.1:5000',
      '/jobs': 'http://127.0.0.1:5000',
      '/validate': 'http://127.0.0.1:5000',
      '/detect-drift': 'http://127.0.0.1:5000',
    },
  },
})