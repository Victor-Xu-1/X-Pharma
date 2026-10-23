import { expect, it, vi } from "vitest";
import { emptyPipelineSearchFilters, savePipelineSearch } from "../lib/contracts/pipeline";
import { setLocale } from "../lib/i18n";

const intent = {
  name: "研究员原名",
  filters: { ...emptyPipelineSearchFilters(), query: "EGFR" },
  analysis: {
    dimension: "targets" as const,
    view: "table" as const,
    limit: 8 as const,
    stageScope: "overall" as const,
    targetAggregation: "all" as const,
  },
  displayMode: "list" as const,
  shared: false,
  monitor: true,
};
function savedResponse() {
  return new Response(JSON.stringify({ id: "saved-1" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

it("returns a locale-independent partial-success identity and literal reason without recreating the saved search", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(savedResponse())
    .mockRejectedValueOnce(new Error("原始 provider <EGFR> reason"));
  setLocale("en");
  const result = await savePipelineSearch(intent);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 provider <EGFR> reason" });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(JSON.parse(String(fetch.mock.calls[1]?.[1]?.body))).toEqual({
    name: "研究员原名",
    saved_search_id: "saved-1",
  });
  setLocale("zh-CN");
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 provider <EGFR> reason" });
  expect(fetch).toHaveBeenCalledTimes(2);
});
it("does not request a monitoring topic when it was not selected", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(savedResponse());
  await expect(savePipelineSearch({ ...intent, monitor: false })).resolves.toEqual({
    kind: "saved",
    monitoring: false,
  });
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("fails the original save rather than attempting to subscribe or declaring a partial success", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Original save rejected"));
  await expect(savePipelineSearch(intent)).rejects.toThrow("Original save rejected");
  expect(fetch).toHaveBeenCalledTimes(1);
});
