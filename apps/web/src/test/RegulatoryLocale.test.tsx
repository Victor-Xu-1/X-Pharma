import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import {
  emptyRegulatorySearchFilters,
  loadRegulatoryEventDetail,
  searchRegulatoryEvents,
} from "../lib/contracts/regulatory";
import { setLocale } from "../lib/i18n";
import { RegulatoryView } from "../views/RegulatoryView";
import { eventId, regulatoryEvent, regulatoryResult } from "./fixtures/regulatoryResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/regulatory", async (original) => ({
  ...(await original<typeof import("../lib/contracts/regulatory")>()),
  searchRegulatoryEvents: vi.fn(),
  loadRegulatoryEventDetail: vi.fn(),
  saveRegulatorySearch: vi.fn(),
}));
const props = {
  initialFilters: { ...emptyRegulatorySearchFilters, query: "VX-101" },
  initialOffset: 0,
  selectedEventId: null,
  comparedEventIds: [],
  onSearchChange: vi.fn(),
  onEventChange: vi.fn(),
  onCompareChange: vi.fn(),
  onOpenEntity: vi.fn(),
};
beforeEach(() => {
  vi.clearAllMocks();
  setLocale("en");
  vi.mocked(searchRegulatoryEvents).mockResolvedValue(regulatoryResult);
  vi.mocked(loadRegulatoryEventDetail).mockResolvedValue(regulatoryEvent);
});

it("localizes regulatory controls and memoized columns without rereading or discarding the query draft", async () => {
  renderWithQueryClient(<RegulatoryView {...props} />);
  const table = await screen.findByRole("table", { name: "Regulatory events" });
  expect(table).toHaveTextContent(regulatoryEvent.title);
  fireEvent.change(screen.getByRole("textbox", { name: "Keyword" }), { target: { value: "未提交监管草稿" } });
  const reads = vi.mocked(searchRegulatoryEvents).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "监管事件结果" })).toBe(table);
  expect(screen.getByRole("textbox", { name: "关键词" })).toHaveValue("未提交监管草稿");
  expect(searchRegulatoryEvents).toHaveBeenCalledTimes(reads);
  expect(props.onSearchChange).not.toHaveBeenCalled();
});

it("does not mistake default display and sort state for a clearable condition", async () => {
  setLocale("zh-CN");
  renderWithQueryClient(<RegulatoryView {...props} initialFilters={emptyRegulatorySearchFilters} />);
  await screen.findByRole("table", { name: "监管事件结果" });
  expect(screen.getByRole("button", { name: "清除" })).toBeDisabled();
});

it("fails closed on a regulatory detail whose identity does not match the selected request", async () => {
  vi.mocked(loadRegulatoryEventDetail).mockResolvedValue({
    ...regulatoryEvent,
    id: "foreign",
    title: "FOREIGN_RECORD",
  });
  renderWithQueryClient(<RegulatoryView {...props} selectedEventId={eventId} />);
  await screen.findByText("Regulatory detail does not match the requested record");
  expect(screen.queryByRole("heading", { name: "FOREIGN_RECORD" })).not.toBeInTheDocument();
});

it("hides cached regulatory detail identity after the current read loses access", async () => {
  const rendered = renderWithQueryClient(<RegulatoryView {...props} selectedEventId={eventId} />);
  await screen.findByRole("dialog", { name: regulatoryEvent.title });
  vi.mocked(loadRegulatoryEventDetail).mockRejectedValue(new ApiError("RAW_ACCESS_DENIED", 403, null));
  await act(async () => {
    await rendered.queryClient.refetchQueries({ queryKey: ["intelligence", "regulatory", "detail", eventId] });
  });
  await screen.findByText("RAW_ACCESS_DENIED");
  expect(screen.queryByRole("dialog", { name: regulatoryEvent.title })).not.toBeInTheDocument();
});

it("keeps all original supplementary fields including zero and false beyond the old two-field summary", async () => {
  const details = { first: "原始信息", second: 0, third: false, fourth: "FOURTH_RAW_FIELD" };
  vi.mocked(loadRegulatoryEventDetail).mockResolvedValue({ ...regulatoryEvent, details });
  renderWithQueryClient(<RegulatoryView {...props} selectedEventId={eventId} />);
  const dialog = await screen.findByRole("dialog", { name: regulatoryEvent.title });
  fireEvent.click(within(dialog).getByText("Complete source metadata", { exact: true }));
  expect(
    within(dialog).getByRole("region", { name: "Complete original source metadata" }).querySelector("pre")?.textContent,
  ).toBe(JSON.stringify(details, null, 2));
});

it("excludes a mismatched comparison response rather than presenting a different event", async () => {
  vi.mocked(loadRegulatoryEventDetail).mockResolvedValue({
    ...regulatoryEvent,
    id: "foreign",
    subject_entity: { ...regulatoryEvent.subject_entity, name: "FOREIGN_SUBJECT" },
  });
  renderWithQueryClient(<RegulatoryView {...props} comparedEventIds={[eventId]} />);
  await screen.findByText("Comparison record does not match the requested record");
  expect(screen.queryByText("FOREIGN_SUBJECT")).not.toBeInTheDocument();
});

it("does not show a cached comparison event after its current authorization is denied", async () => {
  const rendered = renderWithQueryClient(<RegulatoryView {...props} comparedEventIds={[eventId]} />);
  await screen.findByRole("table", { name: "Regulatory event comparison" });
  vi.mocked(loadRegulatoryEventDetail).mockRejectedValue(new ApiError("RAW_COMPARE_DENIED", 403, null));
  await act(async () => {
    await rendered.queryClient.refetchQueries({ queryKey: ["intelligence", "regulatory", "detail", eventId] });
  });
  await screen.findByText("RAW_COMPARE_DENIED");
  expect(screen.queryByRole("table", { name: "Regulatory event comparison" })).not.toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Regulatory events" })).toHaveTextContent(regulatoryEvent.title);
});

it("keeps prototype-like unknown event codes literal and distinguishes a recorded false from missing", async () => {
  const event = { ...regulatoryEvent, event_type: "__proto__", status: "constructor", has_boxed_warning: false };
  vi.mocked(loadRegulatoryEventDetail).mockResolvedValue(event);
  vi.mocked(searchRegulatoryEvents).mockResolvedValue({
    ...regulatoryResult,
    items: [event],
    facets: { ...regulatoryResult.facets, event_type: { ["__proto__"]: 1 } },
  });
  renderWithQueryClient(<RegulatoryView {...props} selectedEventId={eventId} />);
  const dialog = await screen.findByRole("dialog", { name: regulatoryEvent.title });
  expect(dialog).toHaveTextContent("__proto__");
  expect(dialog).toHaveTextContent("constructor");
  const warning = within(dialog).getByText("Boxed warning", { exact: true }).closest("div");
  expect(warning).toHaveTextContent("No");
  expect(warning).not.toHaveTextContent("Not provided");
});
