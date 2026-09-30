import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";

const backendTarget = process.env.WORKBENCH_PROXY_TARGET ?? "http://127.0.0.1:8080";
const backendProxy = {
  "/api": backendTarget,
  "/health": backendTarget,
};

function workbenchEntryRoutes(): Plugin {
  const rewrite = (url: string | undefined) => {
    if (!url) return url;
    const [pathname, query] = url.split("?", 2);
    const entry =
      pathname === "/workspace/research" || pathname === "/workspace/research/"
        ? "/research.html"
        : pathname === "/workspace/internal" || pathname === "/workspace/internal/"
          ? "/internal.html"
          : null;
    return entry ? (query ? `${entry}?${query}` : entry) : url;
  };

  return {
    name: "workbench-entry-routes",
    configureServer(server) {
      server.middlewares.use((request, _response, next) => {
        const currentUrl = request.originalUrl ?? (Reflect.get(request, "url") as string | undefined);
        const rewrittenUrl = rewrite(currentUrl);
        Reflect.set(request, "url", rewrittenUrl);
        request.originalUrl = rewrittenUrl;
        next();
      });
    },
    configurePreviewServer(server) {
      server.middlewares.use((request, _response, next) => {
        const currentUrl = request.originalUrl ?? (Reflect.get(request, "url") as string | undefined);
        const rewrittenUrl = rewrite(currentUrl);
        Reflect.set(request, "url", rewrittenUrl);
        request.originalUrl = rewrittenUrl;
        next();
      });
    },
  };
}

export default defineConfig({
  plugins: [workbenchEntryRoutes(), react()],
  define: { global: "globalThis" },
  resolve: {
    alias: [
      // The small-molecule editor hides these optional scripting/3D paths so the production bundle remains CSP-safe.
      { find: /^paper$/, replacement: new URL("./node_modules/paper/dist/paper-core.js", import.meta.url).pathname },
      { find: "miew-react", replacement: new URL("./src/shims/miew-react-stub.tsx", import.meta.url).pathname },
    ],
  },
  server: {
    port: 5173,
    proxy: backendProxy,
  },
  preview: {
    proxy: backendProxy,
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    clearMocks: true,
    include: ["src/**/*.test.{ts,tsx}"],
    // The jsdom workbench suites are CPU-heavy; higher parallelism makes their real 5s behavior budgets nondeterministic.
    pool: "forks",
    maxWorkers: 1,
  },
  build: {
    manifest: true,
    rollupOptions: {
      input: {
        index: new URL("./index.html", import.meta.url).pathname,
        research: new URL("./research.html", import.meta.url).pathname,
        internal: new URL("./internal.html", import.meta.url).pathname,
      },
    },
  },
});
