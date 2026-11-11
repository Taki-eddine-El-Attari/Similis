import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    // « @ » désigne le dossier src/
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // En développement, les appels /api sont transmis à Flask :
    // le navigateur ne voit qu'une origine, le cookie de session passe sans CORS.
    proxy: { '/api': 'http://127.0.0.1:5000' },
  },
})
