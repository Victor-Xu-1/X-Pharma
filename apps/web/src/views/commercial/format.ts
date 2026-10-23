import { formattingLocale } from "../../lib/i18n";
import { commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";

type DecimalUnits = { coefficient: bigint; scale: number };
/** Parse the server's decimal strings without passing any amount through binary floating point. */
function decimalUnits(value: string): DecimalUnits | null {
  if (typeof value !== "string" || value.length > 256) return null;
  const match = /^([+-]?)(\d+)(?:\.(\d+))?(?:[eE]([+-]?\d+))?$/.exec(value);
  if (!match) return null;
  const fraction = match[3] ?? "",
    exponent = Number(match[4] ?? "0");
  if (!Number.isInteger(exponent) || Math.abs(exponent) > 128) return null;
  const scale = fraction.length - exponent;
  if (scale > 128) return null;
  const coefficient = BigInt(match[2] + fraction) * (match[1] === "-" ? -1n : 1n);
  return scale < 0 ? { coefficient: coefficient * 10n ** BigInt(-scale), scale: 0 } : { coefficient, scale };
}
function decimalText({ coefficient, scale }: DecimalUnits): string {
  const digits = (coefficient < 0n ? -coefficient : coefficient).toString().padStart(scale + 1, "0");
  return (coefficient < 0n ? "-" : "") + (scale ? digits.slice(0, -scale) + "." + digits.slice(-scale) : digits);
}
export function units(value: string | null): string {
  if (value === null) return t("额度数据不可合计");
  const parsed = decimalUnits(value);
  if (!parsed) return t("额度数据不可合计");
  const [whole, fraction] = decimalText(parsed).split(".");
  const grouped = new Intl.NumberFormat(formattingLocale(), { maximumFractionDigits: 0 }).format(BigInt(whole));
  return grouped + (fraction === undefined ? "" : "." + fraction);
}
export function sumUnits(values: readonly string[]): string | null {
  const parsed = values.map(decimalUnits);
  if (parsed.some((value) => value === null)) return null;
  const decimals = parsed.filter((value): value is DecimalUnits => value !== null);
  const scale = Math.max(0, ...decimals.map((value) => value.scale));
  const coefficient = decimals.reduce((sum, value) => sum + value.coefficient * 10n ** BigInt(scale - value.scale), 0n);
  return decimalText({ coefficient, scale });
}
export function reportedCount(value: number | undefined): string {
  return value === undefined ? t("未上报") : String(value);
}
