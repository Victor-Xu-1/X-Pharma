import { expect, it, vi } from "vitest";
import { savedNewsQuery, saveNewsSearch } from "../lib/contracts/news";
import { setLocale } from "../lib/i18n";
import { initialFilters } from "./fixtures/newsResearch";

const intent = { name: "研究员原名", filters: initialFilters, shared: false, monitor: true };
function savedResponse() {
  return new Response(JSON.stringify({ id: "saved-news" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

it("keeps one saved query after subscription failure and returns the original reason independently of locale", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(savedResponse())
    .mockRejectedValueOnce(new Error("原始 provider <EGFR> reason"));
  setLocale("en");
  const result = await saveNewsSearch(intent);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 provider <EGFR> reason" });
  expect(JSON.parse(String(fetch.mock.calls[0]?.[1]?.body))).toEqual({
    name: "研究员原名",
    query_type: "news_search",
    query: savedNewsQuery(initialFilters),
    visibility: "private",
  });
  expect(JSON.parse(String(fetch.mock.calls[1]?.[1]?.body))).toEqual({
    name: "研究员原名",
    saved_search_id: "saved-news",
  });
  setLocale("zh-CN");
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(result).toEqual({ kind: "monitor_failed", reason: "原始 provider <EGFR> reason" });
});

it("does not request monitoring when it was not selected", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(savedResponse());
  await expect(saveNewsSearch({ ...intent, monitor: false })).resolves.toEqual({ kind: "saved", monitoring: false });
  expect(fetch).toHaveBeenCalledTimes(1);
});

it("fails the original save without subscribing or claiming partial success", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Original save rejected"));
  await expect(saveNewsSearch(intent)).rejects.toThrow("Original save rejected");
  expect(fetch).toHaveBeenCalledTimes(1);
});
