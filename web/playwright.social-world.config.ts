import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests-social-world",
  outputDir: "test-results-social-world",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["line"], ["html", { outputFolder: "playwright-report-social-world", open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    viewport: { width: 1280, height: 820 }
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ],
  webServer: [
    {
      command: "python scripts/run_social_world_e2e_server.py",
      cwd: "..",
      url: "http://127.0.0.1:8000/api/health",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        SAM_SEBE_DB: "data/e2e-social-world.sqlite3",
        OPENAI_API_KEY: ""
      }
    },
    {
      command: "npm run dev -- --host 127.0.0.1",
      cwd: ".",
      url: "http://127.0.0.1:5173",
      timeout: 120_000,
      reuseExistingServer: false
    }
  ]
});
