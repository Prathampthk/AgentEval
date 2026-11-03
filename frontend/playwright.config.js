import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
export default defineConfig({
  testDir: "tests",
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:5174/dashboard/",
    headless: true,
    launchOptions: existsSync("/usr/bin/chromium")
      ? { executablePath: "/usr/bin/chromium", args: ["--no-sandbox"] }
      : {},
  },
  webServer: [
    {
      command:
        "AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py demo .venv/bin/uvicorn agenteval.api:app --host 127.0.0.1 --port 8010",
      cwd: "..",
      url: "http://127.0.0.1:8010/health/live",
      reuseExistingServer: false,
    },
    {
      command: "API_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5174",
      url: "http://127.0.0.1:5174/dashboard/",
      reuseExistingServer: false,
    },
  ],
});
