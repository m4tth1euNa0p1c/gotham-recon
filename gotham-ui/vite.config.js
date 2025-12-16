import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 3000,
    proxy: {
      '/graphql': {
        target: 'http://bff-gateway:8080',
        changeOrigin: true
      },
      '/api': {
        target: 'http://recon-orchestrator:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    sourcemap: true
  }
})
