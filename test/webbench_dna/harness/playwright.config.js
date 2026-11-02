// Mirrors projects/dom1/playwright.config.js (production timeouts) but serves nothing itself:
// CANDIDATE_URL points at a locally served candidate directory containing index.html.
const { defineConfig, devices } = require('@playwright/test')
module.exports = defineConfig({
  testDir: './dom1-tests',
  timeout: 12_000,
  expect: { timeout: 3_000 },
  fullyParallel: true,
  workers: Number(process.env.WORKERS || 2),
  retries: 0,
  reporter: [['json', { outputFile: process.env.REPORT_FILE || 'report.json' }]],
  use: { baseURL: process.env.CANDIDATE_URL, trace: 'off', headless: true },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
