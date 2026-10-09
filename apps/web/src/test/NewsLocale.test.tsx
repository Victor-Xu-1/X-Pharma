import { act, fireEvent, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import { loadNewsEventDetail, saveNewsSearch, searchNewsEvents } from "../lib/contracts/news";
import type { SavedSearchCreationOutcome } from "../lib/contracts/savedSearchCreation";
import { setLocale } from "../lib/i18n";
import { NewsView } from "../views/NewsView";
import { initialFilters, newsResult } from "./fixtures/newsResearch";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/news", async (original) => ({
  ...(await original<typeof import("../lib/contracts/news")>()),
  searchNewsEvents: vi.fn(),
  loadNewsEventDetail: vi.fn(),
  saveNewsSearch: vi.fn(),
}));
const props = {
  initialFilters,
  initialOffset: 0,
  selectedNewsEventId: null,
  onSearchChange: vi.fn(),
  onNewsEventChange: vi.fn(),
  onOpenEntity: vi.fn(),
};
beforeEach(() => {
  vi.clearAllMocks();
  setLocale("en");
  vi.mocked(searchNewsEvents).mockResolvedValue(newsResult);
  vi.mocked(loadNewsEventDetail).mockResolvedValue(newsResult.items[0]);
});

it("localizes news controls and memoized headers while keeping source text, drafts and cached reads", async () => {
  renderWithQueryClient(<NewsView {...props} />);
  const table = await screen.findByRole("table", { name: "Research updates" });
  expect(table).toHaveTextContent(newsResult.items[0].title);
  fireEvent.change(screen.getByRole("textbox", { name: "Keyword" }), {
    target: { value: "未提交的原始检索草稿" },
  });
  const reads = vi.mocked(searchNewsEvents).mock.calls.length;
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "新闻与会议结果" })).toHaveTextContent(newsResult.items[0].title);
  expect(screen.getByRole("textbox", { name: "关键词" })).toHaveValue("未提交的原始检索草稿");
  expect(searchNewsEvents).toHaveBeenCalledTimes(reads);
  expect(props.onSearchChange).not.toHaveBeenCalled();
});

it("does not treat display/sort defaults as a clearable query, but permits clearing a real draft", async () => {
  setLocale("zh-CN");
  renderWithQueryClient(<NewsView {...props} initialFilters={{ ...initialFilters, query: "" }} />);
  await screen.findByRole("table", { name: "新闻与会议结果" });
  expect(screen.getByRole("button", { name: "清除" })).toBeDisabled();
  fireEvent.change(screen.getByRole("textbox", { name: "关键词" }), { target: { value: "draft" } });
  expect(screen.getByRole("button", { name: "清除" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "清除" }));
  expect(screen.getByRole("textbox", { name: "关键词" })).toHaveValue("");
});

it("fails closed for a detail response with the wrong record identity", async () => {
  vi.mocked(loadNewsEventDetail).mockResolvedValue({ ...newsResult.items[0], id: "foreign", title: "FOREIGN_RECORD" });
  renderWithQueryClient(<NewsView {...props} selectedNewsEventId="news-1" />);
  await screen.findByText("Update detail does not match the requested record");
  expect(screen.queryByRole("heading", { name: "FOREIGN_RECORD" })).not.toBeInTheDocument();
});

it("shows the latest access-denial reason rather than a previous wrong-identity diagnostic", async () => {
  vi.mocked(loadNewsEventDetail).mockResolvedValue({ ...newsResult.items[0], id: "foreign", title: "FOREIGN_RECORD" });
  const rendered = renderWithQueryClient(<NewsView {...props} selectedNewsEventId="news-1" />);
  await screen.findByText("Update detail does not match the requested record");
  vi.mocked(loadNewsEventDetail).mockRejectedValue(new ApiError("RAW_ACCESS_DENIED", 403, null));
  await act(async () => {
    await rendered.queryClient.refetchQueries({ queryKey: ["intelligence", "news", "detail", "news-1"] });
  });
  expect(await screen.findByText("RAW_ACCESS_DENIED")).toBeInTheDocument();
  expect(screen.queryByText("Update detail does not match the requested record")).not.toBeInTheDocument();
  expect(screen.queryByRole("heading", { name: "FOREIGN_RECORD" })).not.toBeInTheDocument();
});

it("retains complete supplementary source metadata including zero, false and fields beyond the summary", async () => {
  const details = { first: "原始信息", second: 0, third: false, fourth: "literal", fifth: "FIFTH_RAW_FIELD" };
  vi.mocked(loadNewsEventDetail).mockResolvedValue({ ...newsResult.items[0], details });
  renderWithQueryClient(<NewsView {...props} selectedNewsEventId="news-1" />);
  const dialog = await screen.findByRole("dialog", { name: newsResult.items[0].title });
  fireEvent.click(within(dialog).getByText("Complete source metadata", { exact: true }));
  expect(
    within(dialog).getByRole("region", { name: "Complete original source metadata" }).querySelector("pre")?.textContent,
  ).toBe(JSON.stringify(details, null, 2));
  act(() => setLocale("zh-CN"));
  expect(dialog.querySelector("details")).toHaveAttribute("open");
  expect(within(dialog).getByRole("region", { name: "完整原始补充信息" }).querySelector("pre")?.textContent).toBe(
    JSON.stringify(details, null, 2),
  );
});

it("does not reveal a cached detail title or narrative after the current read is forbidden", async () => {
  const rendered = renderWithQueryClient(<NewsView {...props} selectedNewsEventId="news-1" />);
  await screen.findByRole("dialog", { name: newsResult.items[0].title });
  vi.mocked(loadNewsEventDetail).mockRejectedValue(new ApiError("RAW_ACCESS_DENIED", 403, null));
  await act(async () => {
    await rendered.queryClient.refetchQueries({ queryKey: ["intelligence", "news", "detail", "news-1"] });
  });
  await screen.findByText("RAW_ACCESS_DENIED");
  expect(screen.queryByRole("dialog", { name: newsResult.items[0].title })).not.toBeInTheDocument();
  const errorDialog = screen.getByRole("dialog", { name: "Update detail" });
  expect(within(errorDialog).queryByText(newsResult.items[0].summary)).not.toBeInTheDocument();
  expect(screen.getByRole("table", { name: "Research updates" })).toHaveTextContent(newsResult.items[0].summary);
});

it("translates recognized statistic types without rewriting an unknown source bucket", async () => {
  vi.mocked(searchNewsEvents).mockResolvedValue({
    ...newsResult,
    landscape: {
      ...newsResult.landscape,
      event_type: [
        ...newsResult.landscape.event_type,
        { key: "vendor_unknown", label: "原始供应商类型", count: 0, share: 0 },
      ],
    },
  });
  renderWithQueryClient(
    <NewsView {...props} initialFilters={{ ...initialFilters, displayMode: "landscape", analysisView: "table" }} />,
  );
  const table = await screen.findByRole("table", { name: "Update type statistics" });
  expect(table).toHaveTextContent("Publication");
  expect(table).toHaveTextContent("原始供应商类型");
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("table", { name: "事件类型统计表" })).toBe(table);
  expect(table).toHaveTextContent("论文发表");
  expect(table).toHaveTextContent("原始供应商类型");
  expect(searchNewsEvents).toHaveBeenCalledTimes(1);
});

it("retains and locks a pending save across a locale change, then presents partial success in the current language", async () => {
  let finish: (outcome: SavedSearchCreationOutcome) => void = () => {
    throw new Error("No pending save");
  };
  vi.mocked(saveNewsSearch).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  renderWithQueryClient(<NewsView {...props} />);
  await screen.findByRole("table", { name: "Research updates" });
  fireEvent.click(screen.getByRole("button", { name: "Save / monitor" }));
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByRole("textbox", { name: "Name" }), { target: { value: "原始研究名称" } });
  fireEvent.click(within(dialog).getByRole("button", { name: "Save search" }));
  await screen.findByText("Saving search");
  act(() => setLocale("zh-CN"));
  expect(within(dialog).getByRole("textbox", { name: "名称" })).toHaveValue("原始研究名称");
  expect(within(dialog).getByRole("textbox", { name: "名称" })).toBeDisabled();
  for (const option of within(dialog).getAllByRole("checkbox")) expect(option).toBeDisabled();
  fireEvent.keyDown(dialog, { key: "Escape" });
  expect(dialog).toBeInTheDocument();
  expect(saveNewsSearch).toHaveBeenCalledTimes(1);
  await act(async () => finish({ kind: "monitor_failed", reason: "RAW_PROVIDER_REASON" }));
  expect(await screen.findByText("检索已保存，但监控未启用：RAW_PROVIDER_REASON")).toBeInTheDocument();
  act(() => setLocale("en"));
  expect(screen.getByText("Query saved, but monitoring was not enabled: RAW_PROVIDER_REASON")).toBeInTheDocument();
  expect(saveNewsSearch).toHaveBeenCalledTimes(1);
});

it("rejects an inverted publication range without submitting and translates the validation without losing dates", async () => {
  renderWithQueryClient(<NewsView {...props} />);
  await screen.findByRole("table", { name: "Research updates" });
  fireEvent.click(screen.getByText("More filters"));
  fireEvent.change(screen.getByLabelText("Published from"), { target: { value: "2026-12-31" } });
  fireEvent.change(screen.getByLabelText("Published to"), { target: { value: "2026-01-01" } });
  fireEvent.submit(screen.getByRole("form", { name: "Research update filters" }));
  expect(screen.getByRole("alert")).toHaveTextContent("Publication date: the start must not be later than the end");
  expect(props.onSearchChange).not.toHaveBeenCalled();
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("alert")).toHaveTextContent("发布日期起始值不能晚于结束值");
  expect(screen.getByLabelText("发布起始")).toHaveValue("2026-12-31");
  fireEvent.change(screen.getByLabelText("发布截止"), { target: { value: "2026-12-31" } });
  fireEvent.submit(screen.getByRole("form", { name: "新闻与会议筛选" }));
  expect(props.onSearchChange).toHaveBeenCalledExactlyOnceWith(
    { ...initialFilters, publishedFrom: "2026-12-31", publishedTo: "2026-12-31" },
    0,
  );
});
