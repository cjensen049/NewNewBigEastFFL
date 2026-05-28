import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // In development, proxy all /api/* requests to the FastAPI server on port 8000.
    // This means you can run both servers and they work seamlessly together.
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
