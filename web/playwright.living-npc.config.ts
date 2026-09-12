import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests-living-npc",
  outputDir: "test-results-living-npc",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["line"], ["html", { outputFolder: "playwright-report-living-npc", open: "never" }]],
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
      command: "python scripts/run_living_npc_e2e_server.py",
      cwd: "..",
      url: "http://127.0.0.1:8000/api/health",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        ...process.env,
        SAM_SEBE_DB: "data/e2e-living-npc.sqlite3",
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
