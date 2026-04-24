import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

const BACKEND = "http://127.0.0.1:8000";

// Paths that the FastAPI backend owns. Requests hitting these during `vite dev`
// get transparently forwarded so the React app can call the existing API
// without worrying about CORS or hard-coding origins.
const backendProxyPaths = [
  "/api",
  "/auth",
  "/upload_client_doc",
  "/upload_agent_doc",
  "/upload",
  "/review",
  "/requirements",
  "/approve",
  "/export",
  "/static",
  "/uploads",
  "/docs",
  "/openapi.json",
];

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: Object.fromEntries(
      backendProxyPaths.map((p) => [
        p,
        { target: BACKEND, changeOrigin: true, secure: false },
      ]),
    ),
  },
});
