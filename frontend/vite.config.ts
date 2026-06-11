import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em dev, o frontend (5173) faz proxy das chamadas de API para o backend (8000),
// evitando CORS e mantendo o cliente usando caminhos relativos.
const API = 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/analyze': API,
      '/settings': API,
      '/report': API,
      '/health': API,
      '/stage': API,
      '/capabilities': API,
      '/knowledge': API,
      '/compare': API,
    },
  },
})
