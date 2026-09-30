import { defineConfig } from "@playwright/test";

import workspaceConfig from "./playwright.config";

export default defineConfig({
  ...workspaceConfig,
  testIgnore: [],
  testMatch: "account-registration.spec.ts",
  timeout: 60_000,
  workers: 2,
  use: { ...workspaceConfig.use, trace: "off", screenshot: "off" },
});
