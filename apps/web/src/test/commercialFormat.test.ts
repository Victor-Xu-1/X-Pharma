import { expect, it } from "vitest";
import { setLocale } from "../lib/i18n";
import { sumUnits, units } from "../views/commercial/format";

it("keeps sub-cent fractional unit totals without displaying them as zero", () => {
  setLocale("en");
  expect(units(sumUnits(["0.000000001", "0.000000002"]))).toBe("0.000000003");
});
it("adds large decimal quota strings without IEEE-754 rounding", () => {
  setLocale("en");
  expect(units(sumUnits(["9007199254740993.123456", "0.000001"]))).toBe("9,007,199,254,740,993.123457");
});
it("does not silently convert an invalid reported quota to zero", () => {
  expect(sumUnits(["860", "RAW_INVALID_UNITS"])).toBeNull();
});
