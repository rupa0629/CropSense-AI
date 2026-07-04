import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from 'tailwindcss';
import autoprefixer from 'autoprefixer';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}'],
  },
  css: {
    postcss: {
      plugins: [
        tailwindcss({
          content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
          theme: { extend: {} },
          plugins: [],
        }),
        autoprefixer(),
      ],
    },
  },
});

