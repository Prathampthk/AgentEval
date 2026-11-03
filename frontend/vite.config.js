import { defineConfig } from "vite";
const target = process.env.API_TARGET || "http://127.0.0.1:8000";
export default defineConfig({
  base: "/dashboard/",
  server: {
    proxy: Object.fromEntries(
      [
        "/overview",
        "/datasets",
        "/runs",
        "/queued-runs",
        "/comparisons",
        "/judge-validation",
        "/health",
      ].map((path) => [path, { target }]),
    ),
  },
});
