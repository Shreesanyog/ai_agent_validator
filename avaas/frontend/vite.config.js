import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// AVaaS React dashboard. In dev mode (`npm run dev`), API calls to /api/*
// and /health are proxied to the FastAPI backend on :8000 so the dashboard
// and API can be developed/run as two separate processes without CORS
// friction. In production, run `npm run build` and the FastAPI app
// (src/avaas/main.py) will serve the resulting frontend/dist/ directly.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
