import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In development the dashboard runs on :5173 and forwards API calls to the FastAPI
// server on :8000. In production FastAPI serves the built files itself (npm run build).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: { environment: "node" },
});
