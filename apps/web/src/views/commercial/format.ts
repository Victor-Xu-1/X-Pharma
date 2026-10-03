export function units(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

export function sumUnits(values: string[]): number {
  return values.reduce((sum, value) => sum + (Number(value) || 0), 0);
}
