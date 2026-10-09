import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { loadEpidemiologyTrend, searchEpidemiology } from "../lib/contracts/epidemiology";
import { setLocale } from "../lib/i18n";
import { EpidemiologyView } from "../views/EpidemiologyView";
import { emptyFilters, observation, searchResult } from "./fixtures/epidemiologyResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/epidemiology", async (original) => ({
  ...(await original<typeof import("../lib/contracts/epidemiology")>()),
  searchEpidemiology: vi.fn(),
  loadEpidemiologyTrend: vi.fn(),
  saveEpidemiologySearch: vi.fn(),
}));
const props = {
  initialFilters: { ...emptyFilters, query: "NSCLC" },
  initialOffset: 0,
  onSearchChange: vi.fn(),
  onOpenEntity: vi.fn(),
};
beforeEach(() => {
  vi.clearAllMocks();
  setLocale("en");
  vi.mocked(searchEpidemiology).mockResolvedValue(searchResult);
  vi.mocked(loadEpidemiologyTrend).mockResolvedValue({
    disease: observation.disease_entity,
    items: [observation],
    total: 1,
    truncated: false,
    as_of: searchResult.as_of,
    warnings: [],
  });
});

it("localizes controls and columns while keeping the source record and unapplied draft", async () => {
  renderWithQueryClient(<EpidemiologyView {...props} />);
  const table = await screen.findByRole("table", { name: "Epidemiology observations" });
  expect(table).toHaveTextContent(observation.methodology);
  expect(table).toHaveTextContent(observation.patient_population.name);
  fireEvent.change(screen.getByRole("textbox", { name: "Source or method" }), {
    target: { value: "未提交疾病负担草稿" },
  });
  const reads = vi.mocked(searchEpidemiology).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "流行病学结果" })).toBe(table);
  expect(screen.getByRole("textbox", { name: "来源或方法" })).toHaveValue("未提交疾病负担草稿");
  expect(searchEpidemiology).toHaveBeenCalledTimes(reads);
  expect(props.onSearchChange).not.toHaveBeenCalled();
});

it("does not enable Clear for sorting/display defaults, but does enable it for a real draft", async () => {
  setLocale("zh-CN");
  renderWithQueryClient(<EpidemiologyView {...props} initialFilters={emptyFilters} />);
  await screen.findByRole("table", { name: "流行病学结果" });
  expect(screen.getByRole("button", { name: "清除" })).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox", { name: "来源或方法" }), { target: { value: "原始草稿" } });
  expect(screen.getByRole("button", { name: "清除" })).toBeEnabled();
});

it("keeps unknown prototype-like measure codes literal instead of looking up inherited object properties", async () => {
  vi.mocked(searchEpidemiology).mockResolvedValue({
    ...searchResult,
    items: [{ ...observation, measure: "constructor", value: 0, lower_bound: 0, upper_bound: 0 }],
  });
  setLocale("zh-CN");
  renderWithQueryClient(<EpidemiologyView {...props} />);
  const table = await screen.findByRole("table", { name: "流行病学结果" });
  expect(table).toHaveTextContent("constructor");
  expect(table).toHaveTextContent("0 (0-0)");
});

it("does not expose cached facet counts after the current observation query loses access", async () => {
  setLocale("zh-CN");
  const rendered = renderWithQueryClient(<EpidemiologyView {...props} />);
  await screen.findByRole("table", { name: "流行病学结果" });
  expect(screen.getByRole("option", { name: "China (101)" })).toBeInTheDocument();
  vi.mocked(searchEpidemiology).mockRejectedValue(new ApiError("RAW_EPIDEMIOLOGY_DENIAL", 403, null));
  await act(async () =>
    rendered.queryClient.refetchQueries({
      queryKey: ["intelligence", "epidemiology", "search", props.initialFilters, 0],
    }),
  );
  await waitFor(() => {
    expect(screen.queryByRole("table", { name: "流行病学结果" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "China (101)" })).not.toBeInTheDocument();
  });
});

it("refuses a trend response for a different disease rather than labelling it a comparable cohort", async () => {
  vi.mocked(loadEpidemiologyTrend).mockResolvedValue({
    disease: { ...observation.disease_entity, id: "foreign" },
    items: [{ ...observation, unit: "FOREIGN_UNIT" }],
    total: 1,
    truncated: false,
    as_of: searchResult.as_of,
    warnings: [],
  });
  renderWithQueryClient(<EpidemiologyView {...props} />);
  const table = await screen.findByRole("table");
  fireEvent.click(
    within(table).getByRole("button", { name: `View comparable trend for ${observation.disease_entity.name}` }),
  );
  await screen.findByText("Trend response does not match the requested cohort");
  expect(screen.queryByText("FOREIGN_UNIT")).not.toBeInTheDocument();
});
