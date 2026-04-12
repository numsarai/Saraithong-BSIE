import fs from 'fs'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const backendTarget = 'http://127.0.0.1:8757'
const appVersion = fs.readFileSync(path.resolve(__dirname, '../VERSION'), 'utf8').trim() || '0.0.0'

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify(appVersion),
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    port: 6776,
    proxy: {
      '/api': { target: backendTarget, changeOrigin: true },
      '/static': { target: backendTarget, changeOrigin: true },
      '/favicon.ico': { target: backendTarget, changeOrigin: true },
    },
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
})
