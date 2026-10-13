import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";

import routeHeads from "./scripts/route-heads";

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
  },
  // routeHeads: arama motoruna açık rotaların kendi HTML'i (canonical vb.).
  plugins: [react(), routeHeads()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
