import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

// In sviluppo le chiamate /api vanno al backend FastAPI: nessun problema di CORS.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
