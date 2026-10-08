import { beforeEach, expect, it, vi } from "vitest";
import { compactNumber, formatDate, statusLabel } from "../components/common";
import { createTranslator, type MessageKey, t, uiFeedback } from "../lib/i18n";
import { messages } from "../lib/i18n/catalog";
import { entityPreviewMessages } from "../lib/i18n/entityPreview";
import { identityMessages } from "../lib/i18n/identity";
import {
  getLocale,
  getLocaleSnapshot,
  initializeLocale,
  LOCALE_STORAGE_KEY,
  setLocale,
  startLocaleSynchronization,
  subscribeLocale,
} from "../lib/i18n/locale";
import { navigationMessages } from "../lib/i18n/navigation";
import { researchContinuityMessages } from "../lib/i18n/researchContinuity";
import { sharedMessages } from "../lib/i18n/shared";

beforeEach(() => setLocale("zh-CN"));

it("has one owner per message and identical interpolation parameters in both languages", () => {
  const owners = [navigationMessages, identityMessages, sharedMessages].flatMap(Object.keys);
  expect(new Set(owners).size).toBe(owners.length);
  const parameters = (value: string) =>
    [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
  for (const [key, english] of Object.entries(messages)) {
    expect(english.trim(), key).not.toBe("");
    expect(parameters(english), key).toEqual(parameters(key));
  }
});

it.each([entityPreviewMessages, researchContinuityMessages])(
  "keeps feature-local preview/history interpolation complete",
  (catalog) => {
    const parameters = (value: string) =>
      [...value.matchAll(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu)].map((match) => match[1]).sort();
    for (const [key, english] of Object.entries(catalog)) {
      expect(english.trim(), key).not.toBe("");
      expect(parameters(english), key).toEqual(parameters(key));
    }
  },
);

it.each(["zh-CN", "en"] as const)("rejects missing message IDs and parameters in %s", (locale) => {
  setLocale(locale);
  expect(() => t("unregistered-message" as MessageKey)).toThrow("Unknown UI message");
  expect(() => t("{name}的头像")).toThrow("Missing UI message parameter");
});

it("interpolates verbatim names without recursively interpreting placeholders or HTML", () => {
  setLocale("en");
  expect(t("{name}的头像", { name: "<script>{name}</script>中文 EGFR" })).toBe(
    "Avatar for <script>{name}</script>中文 EGFR",
  );
  expect(uiFeedback("未登记的服务端原因 EGFR")).toBe("未登记的服务端原因 EGFR");
});

it("uses the same runtime for a feature-local catalog without altering the common catalog", () => {
  const feature = createTranslator({ "已命中 {count} 项": "{count} matching records" } as const);
  expect(feature("已命中 {count} 项", { count: 3 })).toBe("已命中 3 项");
  setLocale("en");
  expect(feature("已命中 {count} 项", { count: 3 })).toBe("3 matching records");
  expect(Object.hasOwn(messages, "已命中 {count} 项")).toBe(false);
});

it.each(["en", "zh-CN", "invalid", null])("reads only the explicit presentation preference %s", (stored) => {
  const read = vi.spyOn(Storage.prototype, "getItem").mockReturnValue(stored);
  initializeLocale();
  expect(getLocale()).toBe(stored === "zh-CN" ? "zh-CN" : "en");
  expect(read).toHaveBeenCalledExactlyOnceWith(LOCALE_STORAGE_KEY);
  expect(document.documentElement.lang).toBe(getLocale());
});

it("persists only the locale and publishes stable snapshots once per actual change", () => {
  const write = vi.spyOn(Storage.prototype, "setItem");
  const listener = vi.fn(),
    stop = subscribeLocale(listener);
  const chinese = getLocaleSnapshot();
  setLocale("zh-CN");
  expect(getLocaleSnapshot()).toBe(chinese);
  setLocale("en");
  expect(listener).toHaveBeenCalledTimes(1);
  expect(write).toHaveBeenLastCalledWith(LOCALE_STORAGE_KEY, "en");
  expect(write.mock.calls.every(([key]) => key === LOCALE_STORAGE_KEY)).toBe(true);
  stop();
  setLocale("zh-CN");
  expect(listener).toHaveBeenCalledTimes(1);
});

it("keeps switching usable and declares unavailable persistence when storage is blocked", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new DOMException("Blocked", "SecurityError");
  });
  setLocale("en");
  expect(getLocaleSnapshot()).toEqual({ locale: "en", persistence: "unavailable" });
  expect(document.documentElement.lang).toBe("en");
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new DOMException("Blocked", "SecurityError");
  });
  initializeLocale();
  expect(getLocale()).toBe("en");
});

it("synchronizes only this local preference and cleans up the cross-tab listener", () => {
  const read = vi.spyOn(Storage.prototype, "getItem").mockReturnValue("en");
  const stop = startLocaleSynchronization();
  window.dispatchEvent(new StorageEvent("storage", { key: "unrelated", storageArea: window.localStorage }));
  window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_STORAGE_KEY, storageArea: window.sessionStorage }));
  expect(read).not.toHaveBeenCalled();
  window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_STORAGE_KEY, storageArea: window.localStorage }));
  expect(getLocale()).toBe("en");
  expect(read).toHaveBeenCalledExactlyOnceWith(LOCALE_STORAGE_KEY);
  stop();
  read.mockReturnValue("zh-CN");
  window.dispatchEvent(new StorageEvent("storage", { key: LOCALE_STORAGE_KEY, storageArea: window.localStorage }));
  expect(getLocale()).toBe("en");
});

it("does not persist unsupported locales", () => {
  const write = vi.spyOn(Storage.prototype, "setItem");
  expect(() => setLocale("fr" as "en")).toThrow("Unsupported interface locale");
  expect(write).not.toHaveBeenCalled();
});

it("formats numbers, timestamps and controlled statuses without changing invalid or unknown values", () => {
  const date = "2026-10-08T10:00:00Z";
  expect(formatDate(date)).toBe(
    new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(date)),
  );
  expect(statusLabel("verified")).toBe("已查证");
  setLocale("en");
  expect(formatDate(date)).toBe(
    new Intl.DateTimeFormat("en-US", { year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(date)),
  );
  expect(compactNumber(1_500)).toBe("1.5K");
  expect(statusLabel("verified")).toBe("Verified");
  expect(statusLabel("custom_status")).toBe("custom status");
  expect(formatDate("bad-date")).toBe("--");
  expect(formatDate(null)).toBe("--");
});
