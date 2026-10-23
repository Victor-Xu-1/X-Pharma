/** Read-only DTOs have no row IDs. Retain duplicates, with content + duplicate occurrence keys. */
export function sourceRecordRows<Value>(values: readonly Value[]): Array<{ key: string; value: Value }> {
  const occurrences = new Map<string, number>();
  return values.map((value) => {
    const content = JSON.stringify(value);
    const occurrence = occurrences.get(content) ?? 0;
    occurrences.set(content, occurrence + 1);
    return { key: `${content}:${occurrence}`, value };
  });
}
