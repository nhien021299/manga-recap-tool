import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: [
      { find: "@/store", replacement: path.resolve(__dirname, "./src/shared/storage") },
      { find: "@/types", replacement: path.resolve(__dirname, "./src/shared/types") },
      { find: "@/components/ui", replacement: path.resolve(__dirname, "./src/shared/ui") },
      { find: "@", replacement: path.resolve(__dirname, "./src") },
    ],
  },
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
  },
  optimizeDeps: {
    exclude: ['@ffmpeg/ffmpeg', '@ffmpeg/util'],
  },
})
