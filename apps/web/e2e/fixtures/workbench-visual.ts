import { test } from "@playwright/test";

// The audited/zoomed browser must not be reused for pixel/RUM acceptance.
// A worker-fixture signature creates a separate framework-managed environment;
// keep the default launcher, context/page/device options, tracing and teardown.
export const workbenchVisualTest = test.extend<Record<never, never>, { workbenchVisualWorker: string }>({
  workbenchVisualWorker: ["workbench-visual", { scope: "worker", auto: true }],
});
