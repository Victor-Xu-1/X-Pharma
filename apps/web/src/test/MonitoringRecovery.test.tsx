import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { createMonitoringTopic, loadMonitoring, loadSavedSearch, type SavedSearch } from "../lib/contracts/monitoring";
import { MonitoringView } from "../views/MonitoringView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/monitoring", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../lib/contracts/monitoring")>()),
  loadMonitoring: vi.fn(),
  loadSavedSearch: vi.fn(),
  createMonitoringTopic: vi.fn(),
}));

const user = {
  id: "reader",
  tenant_id: "tenant",
  email: "reader@example.test",
  display_name: "Reader",
  role: "analyst" as const,
};
const saved: SavedSearch = {
  id: "shared-search",
  owner_user_id: "owner",
  name: "Shared research",
  description: "",
  query_type: "entity_search",
  query_version: 1,
  query_json: { q: "EGFR", entity_type: "target" },
  visibility: "tenant",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(loadMonitoring).mockResolvedValue({ searches: [saved], topics: [], alerts: [] });
  vi.mocked(loadSavedSearch).mockResolvedValue(saved);
});

it("does not replay cached shared conditions after current access is rejected", async () => {
  vi.mocked(loadSavedSearch).mockRejectedValue(new Error("共享检索已撤回"));
  const open = vi.fn();
  renderWithQueryClient(<MonitoringView user={user} activeTab="searches" onOpenEntity={vi.fn()} onOpenSearch={open} />);
  fireEvent.click(await screen.findByRole("button", { name: "运行 Shared research" }));
  await waitFor(() => expect(loadSavedSearch).toHaveBeenCalledWith(saved.id));
  expect(await screen.findByRole("alert")).toHaveTextContent("共享检索已撤回");
  expect(open).not.toHaveBeenCalled();
});

it("runs the current authorized saved query rather than a stale directory version", async () => {
  const current: SavedSearch = {
    ...saved,
    query_version: 2,
    query_json: { q: "ALK", entity_types: ["target", "drug"], review_status: "verified" },
  };
  vi.mocked(loadSavedSearch).mockResolvedValue(current);
  const open = vi.fn();
  renderWithQueryClient(<MonitoringView user={user} activeTab="searches" onOpenEntity={vi.fn()} onOpenSearch={open} />);
  fireEvent.click(await screen.findByRole("button", { name: "运行 Shared research" }));
  await waitFor(() => expect(open).toHaveBeenCalledWith(current));
});

it("keeps one saved replay in flight and does not navigate after a tab change", async () => {
  let finish!: (value: SavedSearch) => void;
  vi.mocked(loadSavedSearch).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const open = vi.fn();
  renderWithQueryClient(<MonitoringView user={user} onOpenEntity={vi.fn()} onOpenSearch={open} />);
  fireEvent.click(await screen.findByRole("tab", { name: "已保存检索" }));
  const run = screen.getByRole("button", { name: "运行 Shared research" });
  fireEvent.click(run);
  fireEvent.click(run);
  await waitFor(() => expect(loadSavedSearch).toHaveBeenCalledTimes(1));
  expect(run).toBeDisabled();
  expect(screen.getByRole("status")).toHaveTextContent("正在核验检索条件与访问权限");
  fireEvent.click(screen.getByRole("tab", { name: "监控主题" }));
  await act(async () => finish(saved));
  expect(open).not.toHaveBeenCalled();
});

it("does not create a topic from a selection removed by a fresh catalogue", async () => {
  const alternate = { ...saved, id: "alternate", name: "Alternate research" };
  vi.mocked(loadMonitoring).mockResolvedValue({ searches: [saved, alternate], topics: [], alerts: [] });
  const { queryClient } = renderWithQueryClient(
    <MonitoringView user={user} activeTab="topics" onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />,
  );
  fireEvent.change(await screen.findByLabelText("选择已保存检索"), { target: { value: alternate.id } });
  fireEvent.change(screen.getByLabelText("监控主题名称"), { target: { value: "Watch" } });
  await act(async () => {
    queryClient.setQueryData(["monitoring", { unreadOnly: false }], { searches: [], topics: [], alerts: [] });
  });
  await waitFor(() => expect(screen.getByRole("button", { name: "创建主题" })).toBeDisabled());
  fireEvent.click(screen.getByRole("button", { name: "创建主题" }));
  expect(createMonitoringTopic).not.toHaveBeenCalled();
});

it("does not navigate from a saved replay after leaving the monitoring page", async () => {
  let finish!: (value: SavedSearch) => void;
  vi.mocked(loadSavedSearch).mockImplementation(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  const open = vi.fn();
  const { unmount } = renderWithQueryClient(
    <MonitoringView user={user} activeTab="searches" onOpenEntity={vi.fn()} onOpenSearch={open} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "运行 Shared research" }));
  await waitFor(() => expect(loadSavedSearch).toHaveBeenCalledTimes(1));
  unmount();
  await act(async () => finish(saved));
  expect(open).not.toHaveBeenCalled();
});

it("labels monitoring lifecycle without confusing it with account health", async () => {
  const topic = {
    id: "topic-active",
    owner_user_id: user.id,
    saved_search_id: saved.id,
    query_version: 1,
    name: "Active watch",
    active: true,
    created_at: saved.created_at,
    updated_at: saved.updated_at,
  };
  vi.mocked(loadMonitoring).mockResolvedValue({
    searches: [saved],
    topics: [topic, { ...topic, id: "topic-paused", name: "Paused watch", active: false }],
    alerts: [],
  });
  renderWithQueryClient(
    <MonitoringView user={user} activeTab="topics" onOpenEntity={vi.fn()} onOpenSearch={vi.fn()} />,
  );
  expect(await screen.findByText("监控中")).toBeVisible();
  expect(screen.getByText("已暂停")).toBeVisible();
});
