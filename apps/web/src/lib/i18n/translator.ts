import type { MessageParameters } from "./catalog";
import { getLocale } from "./locale";

/** Feature catalogs can stay in their lazy-loaded module instead of the entry bundle. */
export function createTranslator<Catalog extends Readonly<Record<string, string>>>(catalog: Catalog) {
  return (key: keyof Catalog & string, parameters: MessageParameters = {}): string => {
    if (!Object.hasOwn(catalog, key)) throw new TypeError(`Unknown UI message: ${key}`);
    const template = getLocale() === "en" ? catalog[key] : key;
    return template.replace(/\{([a-zA-Z][a-zA-Z0-9_]*)\}/gu, (_, name: string) => {
      if (!Object.hasOwn(parameters, name)) throw new TypeError(`Missing UI message parameter: ${name}`);
      return String(parameters[name]);
    });
  };
}
