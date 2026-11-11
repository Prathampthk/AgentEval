import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";

const deployed = process.env.AGENTEVAL_E2E_URL;
const target = new URL(deployed ?? "http://127.0.0.1:5174");
if (
  target.protocol !== "http:" ||
  !["127.0.0.1", "localhost"].includes(target.hostname)
) {
  throw new Error("Browser tests require a loopback HTTP API");
}
const chromium =
  process.env.AGENTEVAL_E2E_BROWSER ??
  (existsSync("/usr/bin/chromium") ? "/usr/bin/chromium" : undefined);

export default defineConfig({
  testDir: "tests",
  workers: 1,
  use: {
    baseURL: new URL("/dashboard/", target).href,
    headless: true,
    launchOptions: chromium ? { executablePath: chromium } : {},
  },
  webServer: deployed
    ? undefined
    : [
        {
          command:
            "AGENTEVAL_PROVIDER=fake .venv/bin/python scripts/local_db.py demo .venv/bin/uvicorn agenteval.api:app --host 127.0.0.1 --port 8010",
          cwd: "..",
          url: "http://127.0.0.1:8010/health/live",
          reuseExistingServer: false,
        },
        {
          command:
            "API_TARGET=http://127.0.0.1:8010 npm run dev -- --port 5174",
          url: "http://127.0.0.1:5174/dashboard/",
          reuseExistingServer: false,
        },
      ],
});
