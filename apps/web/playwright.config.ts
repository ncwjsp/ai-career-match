import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/resume",
  timeout: 30_000,
  use: { baseURL: "http://127.0.0.1:3100", browserName: "chromium" },
  webServer: {
    command: "node node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100", reuseExistingServer: !process.env.CI, timeout: 120_000,
  },
});
