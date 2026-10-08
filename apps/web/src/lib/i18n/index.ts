import { useSyncExternalStore } from "react";
import { isMessageKey, messages } from "./catalog";
import { getLocale, getLocaleSnapshot, subscribeLocale } from "./locale";
import { createTranslator } from "./translator";

export type { MessageKey, MessageParameters } from "./catalog";
export { getLocale, initializeLocale, type Locale, setLocale, startLocaleSynchronization } from "./locale";
export { createTranslator } from "./translator";

export function useLocale() {
  return useSyncExternalStore(subscribeLocale, getLocaleSnapshot, getLocaleSnapshot);
}

/** Explicit UI messages only. React renders the returned text without HTML interpretation. */
export const t = createTranslator(messages);

/** For retained UI feedback and server errors; never pass researcher content here. */
export function uiFeedback(value: string): string {
  return isMessageKey(value) ? t(value) : value;
}

export function formattingLocale(): "zh-CN" | "en-US" {
  return getLocale() === "en" ? "en-US" : "zh-CN";
}
