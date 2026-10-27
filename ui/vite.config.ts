/// <reference types="vitest/config" />
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const root = fileURLToPath(new URL(".", import.meta.url));
const core = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    // The browser talks to the dev server, which forwards to the Python core, so
    // the API sees a same-machine request from an allowed origin (no CORS).
    proxy: {
      "/run": core,
      "/approve": core,
      "/health": core,
      "/events": { target: core, ws: true },
    },
    // `?mock=<path to a run .jsonl>` reads recorded runs from inside the repo only
    // (never ~/.halo, which holds the API token).
    fs: { allow: [resolve(root, "..")] },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
  },
});
