import type { Locator, Page } from "@playwright/test";

/** Shared user-visible identity; styling classes do not own the clinical contract. */
export function linkedTrialProgramDisclosure(page: Page, form: Locator, caption: string) {
  return form.locator("details").filter({ has: page.getByText(caption, { exact: true }) });
}
