import { expect, it, vi } from "vitest";
import { emptyRegulatorySearchFilters, savedRegulatoryQuery, saveRegulatorySearch } from "../lib/contracts/regulatory";
import { setLocale } from "../lib/i18n";

const intent = {
  name: "研究员原名",
  filters: { ...emptyRegulatorySearchFilters, query: "EGFR", boxedWarning: "false" },
  shared: false,
  monitor: true,
};
function savedResponse() {
  return new Response(JSON.stringify({ id: "saved-regulatory" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

it("keeps one regulatory save and its original false filter when monitoring fails", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(savedResponse())
    .mockRejectedValueOnce(new Error("原始 provider <EGFR> reason"));
  setLocale("en");
  const result = await saveRegulatorySearch(intent);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 provider <EGFR> reason" });
  expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
    name: intent.name,
    query_type: "regulatory_search",
    query: savedRegulatoryQuery(intent.filters),
    visibility: "private",
  });
  expect(JSON.parse(String(fetch.mock.calls[1]?.[1]?.body))).toEqual({
    name: intent.name,
    saved_search_id: "saved-regulatory",
  });
  setLocale("zh-CN");
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 provider <EGFR> reason" });
});

it("does not subscribe a regulatory query when monitoring was not selected", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(savedResponse());
  await expect(saveRegulatorySearch({ ...intent, monitor: false })).resolves.toEqual({
    kind: "saved",
    monitoring: false,
  });
  expect(fetch).toHaveBeenCalledOnce();
});

it("does not subscribe or claim partial success when the regulatory save itself fails", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Original regulatory save rejected"));
  await expect(saveRegulatorySearch(intent)).rejects.toThrow("Original regulatory save rejected");
  expect(fetch).toHaveBeenCalledOnce();
});
