import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 4,
  reporter: "list",
  use: {
    baseURL: "http://localhost:3010",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
    { name: "Mobile Safari - iPhone 14", use: { ...devices["iPhone 14"] } },
    { name: "Mobile Chrome - Pixel 5", use: { ...devices["Pixel 5"] } },
  ],
  webServer: {
    command: "npm run dev -- --port 3010",
    url: "http://localhost:3010",
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
})
