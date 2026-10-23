/** Presentation counts stay unknown when an authoritative observation is absent or unsafe. */
export function queueCount(value: unknown, key: string): number | null {
  if (!value || typeof value !== "object" || Array.isArray(value) || !Object.hasOwn(value, key)) return null;
  const count = (value as Record<string, unknown>)[key];
  return typeof count === "number" && Number.isSafeInteger(count) && count >= 0 ? count : null;
}

export function deliveryDeadCount(value: unknown): number | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  let total = 0;
  for (const states of Object.values(value)) {
    const count = queueCount(states, "dead");
    if (count === null || !Number.isSafeInteger(total + count)) return null;
    total += count;
  }
  return total;
}
