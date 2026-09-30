import { defineConfig, devices } from "@playwright/test";

const browserExecutable = process.env.E2E_BROWSER_EXECUTABLE ?? process.env.E2E_CHROME_EXECUTABLE;

export default defineConfig({
  testDir: "./e2e",
  snapshotPathTemplate: "{testDir}/visual-baselines/{arg}-{projectName}{ext}",
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  expect: { timeout: 10_000 },
  reporter: "line",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://127.0.0.1:8080",
    channel: browserExecutable ? undefined : (process.env.E2E_BROWSER_CHANNEL ?? "chrome"),
    launchOptions: browserExecutable ? { executablePath: browserExecutable } : undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "desktop-1440",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } },
    },
    {
      name: "desktop-1920",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1920, height: 1080 } },
    },
    {
      name: "tablet-1024",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1024, height: 768 } },
    },
    {
      name: "mobile-390",
      use: { ...devices["Pixel 7"], viewport: { width: 390, height: 844 } },
    },
  ],
});
