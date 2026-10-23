import { expect, it, vi } from "vitest";
import { saveEntitySearch } from "../lib/contracts/intelligence";
import { setLocale } from "../lib/i18n";

const intent = {
  name: "Original EGFR 科研",
  query: " EGFR ",
  entityTypes: ["target"],
  reviewStatus: "verified",
  sortBy: "name" as const,
  sortDirection: "asc" as const,
  displayMode: "landscape" as const,
  analysisView: "table" as const,
  shared: false,
  monitor: true,
};
const saved = () =>
  new Response(JSON.stringify({ id: "saved-1" }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });

it("returns a locale-independent partial identity and literal reason without repeating the persisted search", async () => {
  const fetch = vi
    .spyOn(globalThis, "fetch")
    .mockResolvedValueOnce(saved())
    .mockRejectedValueOnce(new Error("Original <EGFR> 科研 reason"));
  setLocale("en");
  const outcome = await saveEntitySearch(intent);
  expect(outcome).toEqual({ kind: "monitor_failed", reason: "Original <EGFR> 科研 reason" });
  expect(fetch).toHaveBeenCalledTimes(2);
  expect(JSON.parse(String(fetch.mock.calls[1]?.[1]?.body))).toEqual({ name: intent.name, saved_search_id: "saved-1" });
  setLocale("zh-CN");
  expect(outcome).toEqual({ kind: "monitor_failed", reason: "Original <EGFR> 科研 reason" });
  expect(fetch).toHaveBeenCalledTimes(2);
});
it("returns an explicit saved identity without creating an unselected monitoring topic", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(saved());
  await expect(saveEntitySearch({ ...intent, monitor: false })).resolves.toEqual({ kind: "saved", monitoring: false });
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("returns an explicit saved-and-monitored identity only after both operations finish", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(saved()).mockResolvedValueOnce(saved());
  await expect(saveEntitySearch(intent)).resolves.toEqual({ kind: "saved", monitoring: true });
  expect(fetch).toHaveBeenCalledTimes(2);
});
it("keeps an original save rejection distinct from a partial monitoring outcome", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("Original save rejection"));
  await expect(saveEntitySearch(intent)).rejects.toThrow("Original save rejection");
  expect(fetch).toHaveBeenCalledTimes(1);
});
it("keeps a missing provider reason structured rather than pretranslating an unknown error", async () => {
  const fetch = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(saved()).mockRejectedValueOnce(null);
  await expect(saveEntitySearch(intent)).resolves.toEqual({ kind: "monitor_failed", reason: null });
  expect(fetch).toHaveBeenCalledTimes(2);
});
