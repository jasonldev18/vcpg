import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  // 127.0.0.1 only, never 0.0.0.0 (SECURITY.md section 8)
  server: { host: '127.0.0.1', port: 5173, strictPort: true },
  preview: { host: '127.0.0.1', port: 5173, strictPort: true },
  test: { environment: 'jsdom', setupFiles: ['src/test-setup.ts'] },
})
