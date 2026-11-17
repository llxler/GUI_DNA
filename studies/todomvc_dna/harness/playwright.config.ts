import { defineConfig } from '@playwright/test';

// Runs the official create-playwright TodoMVC demo spec against CANDIDATE_URL (a locally served candidate page).
export default defineConfig({
  testDir: '.',
  testMatch: 'demo-todo-app.spec.ts',
  fullyParallel: true,
  workers: Number(process.env.WORKERS || 4),
  retries: 0,
  timeout: 15000,
  expect: { timeout: 3000 },
  reporter: [['json', { outputFile: process.env.REPORT_FILE || 'report.json' }]],
  use: { browserName: 'chromium', headless: true, trace: 'off', screenshot: 'off', video: 'off' },
});
