import { expect, type Locator } from "@playwright/test";

/** Entity suggestions own explicit listboxes; native select popups do not. */
export async function expectDistinctEntityComboboxes(container: Locator, count: number) {
  const comboboxes = container.getByRole("combobox");
  await expect(comboboxes).toHaveCount(count);
  const listboxes = await comboboxes.evaluateAll((inputs) =>
    inputs.map((input) => input.getAttribute("aria-controls")),
  );
  expect(listboxes.every(Boolean)).toBe(true);
  expect(new Set(listboxes).size).toBe(listboxes.length);
}
