import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import { initializeLocale } from "../lib/i18n";
import { LOCALE_STORAGE_KEY } from "../lib/i18n/locale";

// Existing copy assertions explicitly exercise Chinese, not the product default.
// The locale suites separately verify English-first startup and saved preferences.
beforeEach(() => {
  window.localStorage.setItem(LOCALE_STORAGE_KEY, "zh-CN");
  initializeLocale();
  window.localStorage.removeItem(LOCALE_STORAGE_KEY);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});
