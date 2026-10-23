export function formatAttribute(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (["string", "number", "boolean"].includes(typeof value)) return String(value);
  return JSON.stringify(value);
}
