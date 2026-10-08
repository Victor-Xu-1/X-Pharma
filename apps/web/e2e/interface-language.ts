import { expect, type Page } from "@playwright/test";
import type { Locale } from "../src/lib/i18n/locale";

/** Explicit UI choice for copy-dependent scenarios; never preload or inject storage. */
export async function selectInterfaceLanguage(page: Page, locale: Locale) {
  await page.getByRole("combobox", { name: /^(界面语言|Interface language)$/ }).selectOption(locale);
  await expect(page.locator("html")).toHaveAttribute("lang", locale);
}
