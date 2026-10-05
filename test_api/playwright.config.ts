import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './',
  use: {
    baseURL: process.env.BASE_URL || 'http://127.0.0.1:8000', // đổi theo môi trường của bạn
    extraHTTPHeaders: { 'Content-Type': 'application/json' },
  },
  reporter: [['html'], ['list']],
});
