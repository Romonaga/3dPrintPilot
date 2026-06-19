import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backendPort = process.env.PRINTPILOT_BACKEND_PORT ?? "8002";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 8001,
    allowedHosts: ["3dprintpilot.local", "3dprintpilot"],
    proxy: {
      "/api": `http://127.0.0.1:${backendPort}`
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts"
  }
});
