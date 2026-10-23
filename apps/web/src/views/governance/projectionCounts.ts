function record(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}
export function projectionCountRows(result: Record<string, unknown>) {
  const expected = record(result.expected_counts),
    actual = record(result.actual_counts);
  return [...new Set([...Object.keys(expected ?? {}), ...Object.keys(actual ?? {})])].map((kind) => ({
    kind,
    expected: expected && Object.hasOwn(expected, kind) ? expected[kind] : undefined,
    actual: actual && Object.hasOwn(actual, kind) ? actual[kind] : undefined,
  }));
}
export function projectionCountValue(value: unknown, missing: string): string {
  if (value === undefined || value === null) return missing;
  return typeof value === "number" ? String(value) : (JSON.stringify(value) ?? missing);
}
