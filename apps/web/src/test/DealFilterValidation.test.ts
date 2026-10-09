import { expect, it, vi } from "vitest";
import {
  emptyDealSearchFilters,
  hasDealSearchFilter,
  saveDealSearch,
  searchDeals,
  validateDealSearchFilters,
} from "../lib/contracts/deals";
import { setLocale } from "../lib/i18n";
import { professionalValidationText } from "../lib/i18n/professionalValidation";
import { parseWorkbenchLocation, workspaceUrl } from "../lib/workspaceRouting";

it.each([
  ["首付款必须是有限的非负十进制金额", "Upfront amount: enter a finite, non-negative decimal amount"],
  ["初始披露日期必须是有效的日历日期", "Initial disclosure date: enter a valid calendar date"],
  ["交易状态包含不支持的筛选值", "Deal status: this filter value is not supported"],
])("localizes the owned deal validation %s but leaves original error prose untouched", (message, english) => {
  setLocale("en");
  expect(professionalValidationText(message)).toBe(english);
  expect(professionalValidationText("原始来源失败 <RAW>")).toBe("原始来源失败 <RAW>");
  setLocale("zh-CN");
  expect(professionalValidationText(message)).toBe(message);
});

it.each(["not-a-number", "Infinity", "-1", "0x20", "1e999", "1e-999", "0".repeat(121)])(
  "rejects an unsupported deal amount %s without dropping the condition",
  (value) => {
    const filters = { ...emptyDealSearchFilters, upfrontAmountMin: value, currency: "USD" };
    expect(validateDealSearchFilters(filters)).toBe("首付款必须是有限的非负十进制金额");
    expect(hasDealSearchFilter(filters)).toBe(true);
  },
);

it("requires a currency for every amount sort criterion and every explicit amount including zero", () => {
  expect(validateDealSearchFilters({ ...emptyDealSearchFilters, upfrontAmountMin: "0" })).toBe(
    "按交易金额查询时必须选择币种",
  );
  expect(
    validateDealSearchFilters({
      ...emptyDealSearchFilters,
      sortBy: "name",
      sortDirection: "asc",
      sort: [
        { field: "name", direction: "asc" },
        { field: "upfront_amount", direction: "desc" },
      ],
    }),
  ).toBe("按交易金额排序时必须选择币种");
});

it("rejects a currency that the URL cannot represent instead of discarding it", () => {
  expect(validateDealSearchFilters({ ...emptyDealSearchFilters, currency: "RAW_SOURCE_CURRENCY" })).toBe(
    "币种必须是三位大写字母代码",
  );
  expect(validateDealSearchFilters({ ...emptyDealSearchFilters, currency: "ZZZ" })).toBeNull();
});

it.each(["2026-02-30", "2026-13-01", "2026-1-01"])("rejects an impossible or malformed disclosure day %s", (value) => {
  expect(validateDealSearchFilters({ ...emptyDealSearchFilters, announcedFrom: value })).toBe(
    "初始披露日期必须是有效的日历日期",
  );
});

it("retains exact valid zero, decimal and exponential values and valid leap days", () => {
  expect(
    validateDealSearchFilters({
      ...emptyDealSearchFilters,
      upfrontAmountMin: "0",
      upfrontAmountMax: "1.23456789e-4",
      currency: "USD",
      announcedFrom: "2024-02-29",
    }),
  ).toBeNull();
});

it.each(["0.000123456", "1.23456789e-4", "0"])(
  "round-trips the exact deal amount draft %s through the URL",
  (value) => {
    const initial = {
      workbench: "research" as const,
      view: "deals" as const,
      query: "",
      entityType: "",
      reviewStatus: "",
      entityId: null,
      invalidEntityId: false,
      dealCurrency: "USD",
      dealUpfrontAmountMin: value,
    };
    const url = workspaceUrl(initial);
    expect(new URL(url, "http://localhost").searchParams.get("upfront_amount_min")).toBe(value);
    expect(parseWorkbenchLocation("research", new URL(url, "http://localhost").search)).toMatchObject({
      dealCurrency: "USD",
      dealUpfrontAmountMin: value,
    });
  },
);

it("rejects an unsupported request status without rewriting original result status codes", async () => {
  const filters = { ...emptyDealSearchFilters, status: "constructor" };
  expect(validateDealSearchFilters(filters)).toBe("交易状态包含不支持的筛选值");
  const request = vi.spyOn(globalThis, "fetch");
  await expect(searchDeals(filters, 0, 8)).rejects.toThrow("交易状态包含不支持的筛选值");
  await expect(
    saveDealSearch({
      name: "Original name",
      filters,
      displayMode: "list",
      analysis: { dimension: "all", view: "table", limit: 8 },
      shared: false,
      monitor: false,
    }),
  ).rejects.toThrow("交易状态包含不支持的筛选值");
  expect(request).not.toHaveBeenCalled();
});
