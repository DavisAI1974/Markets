import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    allowedHosts: true,
    proxy: {
      "/mw/evolve-request": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mw/, "/api"),
      },
      "/mw/evolve-requests": {
        target: "http://localhost:8001",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mw/, "/api"),
      },
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/r": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: () => "/api/market-reads",
      },
      "/assets/mw-live.mjs": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: () => "/api/market-reads.mjs",
      },
      "/mw": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/mw/, "/api"),
      },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
