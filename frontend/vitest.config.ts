import path from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
      // Next.js resolves "server-only" to a no-op via the "react-server" export
      // condition at build time; vitest runs under plain Node, so without this
      // alias any module (e.g. bff-response.ts) that imports "server-only" would
      // throw immediately when loaded in a test.
      "server-only": path.resolve(__dirname, "node_modules/server-only/empty.js"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: [
      "src/**/*.test.ts",
      "src/**/*.test.tsx",
      "features/**/*.test.ts",
      "features/**/*.test.tsx",
      "components/**/*.test.ts",
      "components/**/*.test.tsx",
      "app/**/*.test.ts",
      "app/**/*.test.tsx",
      "providers/**/*.test.ts",
      "providers/**/*.test.tsx",
    ],
    exclude: ["e2e/**", "node_modules/**"],
  },
});
