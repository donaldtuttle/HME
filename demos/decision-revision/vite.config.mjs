import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  base: './',
  build: { outDir: 'dist/client' },
  plugins: [react(), tailwindcss()],
  server: { host: '0.0.0.0' },
});
