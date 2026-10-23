import type { MessageParameters } from "./catalog";
import { getLocale, type Locale } from "./locale";

/** Feature catalogs can stay in their lazy-loaded module instead of the entry bundle. */
export function createTranslator<Catalog extends Readonly<Record<string, string>>>(catalog: Catalog) {
  return (key: keyof Catalog & string, parameters: MessageParameters = {}, locale: Locale = getLocale()): string => {
    if (!Object.hasOwn(catalog, key)) throw new TypeError(`Unknown UI message: ${key}`);
    const template = locale === "en" ? catalog[key] : key;
    return template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu, (_, name: string) => {
      if (!Object.hasOwn(parameters, name)) throw new TypeError(`Missing UI message parameter: ${name}`);
      return String(parameters[name]);
    });
  };
}
