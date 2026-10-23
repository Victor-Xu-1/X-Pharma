import { expect, it, vi } from "vitest";
import { savedEpidemiologyQuery, saveEpidemiologySearch } from "../lib/contracts/epidemiology";
import { setLocale } from "../lib/i18n";
import { emptyFilters } from "./fixtures/epidemiologyResearch";

const intent = { name: "原始研究名称", filters: { ...emptyFilters, query: "NSCLC" }, shared: false, monitor: true };
const saved = () =>
  new Response(JSON.stringify({ id: "controlled-epi-save" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

it("keeps one saved epidemiology query when subscription fails and preserves the original reason", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(saved())
    .mockRejectedValueOnce(new Error("原始 SOURCE_REASON"));
  setLocale("en");
  const result = await saveEpidemiologySearch(intent);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 SOURCE_REASON" });
  expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
    name: intent.name,
    query_type: "epidemiology_search",
    query: savedEpidemiologyQuery(intent.filters),
    visibility: "private",
  });
  expect(JSON.parse(String(fetch.mock.calls[1]?.[1]?.body))).toEqual({
    name: intent.name,
    saved_search_id: "controlled-epi-save",
  });
  setLocale("zh-CN");
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 SOURCE_REASON" });
});

it("does not subscribe when monitoring was not selected", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(saved());
  await expect(saveEpidemiologySearch({ ...intent, monitor: false })).resolves.toEqual({
    kind: "saved",
    monitoring: false,
  });
  expect(fetch).toHaveBeenCalledOnce();
});

it("does not subscribe or claim partial success after the save itself fails", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("RAW_EPI_SAVE_FAILURE"));
  await expect(saveEpidemiologySearch(intent)).rejects.toThrow("RAW_EPI_SAVE_FAILURE");
  expect(fetch).toHaveBeenCalledOnce();
});
