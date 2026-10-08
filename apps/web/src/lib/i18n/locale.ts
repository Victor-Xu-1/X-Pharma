export type Locale = "zh-CN" | "en";
export const LOCALE_STORAGE_KEY = "x-pharma.ui.locale";
export const DEFAULT_LOCALE: Locale = "en";
type LocaleSnapshot = Readonly<{ locale: Locale; persistence: "available" | "unavailable" }>;
let snapshot: LocaleSnapshot = { locale: DEFAULT_LOCALE, persistence: "available" };
const listeners = new Set<() => void>();

export function isLocale(value: unknown): value is Locale {
  return value === "zh-CN" || value === "en";
}
export function getLocaleSnapshot(): LocaleSnapshot {
  return snapshot;
}
export function getLocale(): Locale {
  return snapshot.locale;
}
export function subscribeLocale(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}
function publish(locale: Locale, persistence: LocaleSnapshot["persistence"]) {
  if (typeof document !== "undefined") document.documentElement.lang = locale;
  if (snapshot.locale === locale && snapshot.persistence === persistence) return;
  snapshot = { locale, persistence };
  for (const listener of listeners) listener();
}
/** Only a presentation preference is persisted. No credentials, facts or queries. */
export function initializeLocale(): void {
  if (typeof window === "undefined") return;
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    publish(isLocale(stored) ? stored : DEFAULT_LOCALE, "available");
  } catch {
    publish(snapshot.locale, "unavailable");
  }
}
export function setLocale(locale: Locale): void {
  if (!isLocale(locale)) throw new TypeError("Unsupported interface locale");
  let persistence: LocaleSnapshot["persistence"] = "available";
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    persistence = "unavailable";
  }
  publish(locale, persistence);
}
export function startLocaleSynchronization(): () => void {
  function changed(event: StorageEvent) {
    if (event.key !== LOCALE_STORAGE_KEY && event.key !== null) return;
    try {
      if (event.storageArea !== window.localStorage) return;
      const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
      publish(isLocale(stored) ? stored : DEFAULT_LOCALE, "available");
    } catch {
      publish(snapshot.locale, "unavailable");
    }
  }
  window.addEventListener("storage", changed);
  return () => window.removeEventListener("storage", changed);
}
