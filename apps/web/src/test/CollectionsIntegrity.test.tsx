import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { ApiError } from "../lib/api";
import {
  type CollectionDetail,
  getComparisonSet,
  listCollectionVersions,
  loadCollectionCatalog,
  updateComparisonSet,
} from "../lib/contracts/collections";
import { CollectionsView } from "../views/CollectionsView";

vi.mock("../lib/contracts/collections", () => ({
  collectionsKeys: {
    all: ["collections"],
    sets: ["collections", "sets"],
    catalogs: ["collections", "catalog"],
    catalog: (q: string, offset: number) => ["collections", "catalog", q, offset],
    versions: (id: string) => ["collections", "versions", id],
    detail: (id: string) => ["collections", "sets", id],
    policy: ["collections", "policy"],
    search: (q: string) => ["collections", "search", q],
  },
  loadCollectionCatalog: vi.fn(),
  getComparisonSet: vi.fn(),
  getWorkspaceExportPolicy: vi.fn(async () => null),
  searchCollectionEntities: vi.fn(),
  createComparisonSet: vi.fn(),
  addComparisonSetMember: vi.fn(),
  removeComparisonSetMember: vi.fn(),
  updateComparisonSet: vi.fn(),
  exportComparisonSet: vi.fn(),
  listCollectionVersions: vi.fn(async () => []),
}));

const first: CollectionDetail = {
  id: "11111111-1111-4111-8111-111111111111",
  owner_user_id: "owner",
  name: "First list",
  description: "",
  visibility: "private",
  version: 1,
  member_count: 0,
  editable: true,
  members: [],
  created_at: "2026-10-04T00:00:00Z",
  updated_at: "2026-10-04T00:00:00Z",
};
const second: CollectionDetail = { ...first, id: "22222222-2222-4222-8222-222222222222", name: "Second list" };

beforeEach(() => {
  vi.mocked(loadCollectionCatalog).mockResolvedValue({
    items: [first, second],
    total: [first, second].length,
    limit: 25,
    offset: 0,
  });
  vi.mocked(getComparisonSet).mockImplementation(async (id) => (id === second.id ? second : first));
});

function setup(id: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const navigate = vi.fn();
  const view = (active: string) => (
    <QueryClientProvider client={queryClient}>
      <CollectionsView
        activeCollectionId={active}
        comparedEntityIds={[]}
        onLocationChange={navigate}
        onOpenEntity={vi.fn()}
      />
    </QueryClientProvider>
  );
  const result = render(view(id));
  return { ...result, navigate, switchTo: (active: string) => result.rerender(view(active)), queryClient };
}

it("loads an explicit collection independently of the catalog window", async () => {
  const old = { ...first, id: "33333333-3333-4333-8333-333333333333", name: "Older list" };
  vi.mocked(getComparisonSet).mockResolvedValue(old);
  const result = setup(old.id);
  await screen.findByText("Older list");
  expect(getComparisonSet).toHaveBeenCalledWith(old.id, expect.any(AbortSignal));
  expect(result.navigate).not.toHaveBeenCalled();
});

it("does not replace a missing link with a different collection", async () => {
  const missing = "44444444-4444-4444-8444-444444444444";
  vi.mocked(getComparisonSet).mockRejectedValue(new Error("List not found"));
  const result = setup(missing);
  await screen.findByText("List not found");
  expect(getComparisonSet).toHaveBeenCalledWith(missing, expect.any(AbortSignal));
  expect(result.navigate).not.toHaveBeenCalled();
});

it("does not navigate away when a write to the old collection completes", async () => {
  let resolveWrite!: (value: CollectionDetail) => void;
  vi.mocked(updateComparisonSet).mockImplementation(
    () =>
      new Promise((resolve) => {
        resolveWrite = resolve;
      }),
  );
  const result = setup(first.id);
  fireEvent.click(await screen.findByRole("button", { name: "团队共享" }));
  await waitFor(() => expect(updateComparisonSet).toHaveBeenCalled());
  result.switchTo(second.id);
  await waitFor(() => expect(getComparisonSet).toHaveBeenCalledWith(second.id, expect.any(AbortSignal)));
  await act(async () => resolveWrite({ ...first, version: 2, visibility: "tenant" }));
  expect(result.navigate).not.toHaveBeenCalledWith(first.id, expect.anything());
  expect(result.queryClient.getQueryData(["collections", "sets", first.id])).toMatchObject({ version: 2 });
});

it("excludes internal identifiers from the member table", async () => {
  const entity = {
    id: "55555555-5555-4555-8555-555555555555",
    canonical_entity_id: "55555555-5555-4555-8555-555555555555",
    name: "Audit target",
    entity_type: "target" as const,
    description: "",
    review_status: "verified" as const,
    external_ids: { uniprot: "P00533", internal_record: "PRIVATE-IDENTIFIER" },
    attributes: {},
    created_at: first.created_at,
    updated_at: first.updated_at,
  };
  vi.mocked(getComparisonSet).mockResolvedValue({
    ...first,
    member_count: 1,
    members: [{ id: "member", position: 0, added_by_user_id: "owner", created_at: first.created_at, entity }],
  });
  setup(first.id);
  await screen.findByRole("table", { name: "对比列表内容" });
  expect(screen.getByText(/P00533/)).toBeVisible();
  expect(screen.queryByText(/PRIVATE-IDENTIFIER/)).not.toBeInTheDocument();
});

it("saves a name and description through the existing versioned contract", async () => {
  vi.mocked(updateComparisonSet).mockResolvedValue({
    ...first,
    version: 2,
    name: "Renamed list",
    description: "Research scope",
  });
  setup(first.id);
  fireEvent.click(await screen.findByRole("button", { name: "编辑列表" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "  Renamed list  " } });
  fireEvent.change(screen.getByLabelText("业务说明"), { target: { value: "  Research scope  " } });
  fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
  await waitFor(() =>
    expect(updateComparisonSet).toHaveBeenCalledWith(first.id, {
      expected_version: 1,
      name: "Renamed list",
      description: "Research scope",
    }),
  );
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByText("Research scope")).toBeVisible();
});

it("refreshes a conflicting target without discarding the edit draft or retrying a write", async () => {
  vi.mocked(updateComparisonSet).mockRejectedValue(new ApiError("changed", 409, null));
  const result = setup(first.id);
  fireEvent.click(await screen.findByRole("button", { name: "编辑列表" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "My draft" } });
  vi.mocked(getComparisonSet).mockResolvedValue({ ...first, version: 2, name: "Other edit" });
  fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
  await screen.findAllByText(/请核对后重新提交/);
  expect(screen.getByLabelText("名称")).toHaveValue("My draft");
  expect(updateComparisonSet).toHaveBeenCalledTimes(1);
  expect(result.queryClient.getQueryData(["collections", "sets", first.id])).toMatchObject({ version: 2 });
});

it("does not expose metadata writes or history for a shared read-only list", async () => {
  vi.mocked(getComparisonSet).mockResolvedValue({ ...first, editable: false, visibility: "tenant" });
  setup(first.id);
  await screen.findByText("共享列表 · 只读");
  expect(screen.queryByRole("button", { name: "编辑列表" })).not.toBeInTheDocument();
  expect(screen.queryByText("列表变更历史")).not.toBeInTheDocument();
  expect(listCollectionVersions).not.toHaveBeenCalled();
});

it("keeps the edit draft when conflict recovery cannot refresh the version", async () => {
  vi.mocked(updateComparisonSet).mockRejectedValue(new ApiError("changed", 409, null));
  setup(first.id);
  fireEvent.click(await screen.findByRole("button", { name: "编辑列表" }));
  fireEvent.change(screen.getByLabelText("名称"), { target: { value: "Offline draft" } });
  vi.mocked(getComparisonSet).mockRejectedValue(new ApiError("Gateway unavailable", 503, null));
  fireEvent.click(screen.getByRole("button", { name: "保存修改" }));
  await screen.findAllByText(/刷新失败/);
  expect(screen.getByLabelText("名称")).toHaveValue("Offline draft");
  expect(updateComparisonSet).toHaveBeenCalledTimes(1);
});

it("loads owner history lazily and uses a bounded version cursor", async () => {
  vi.mocked(listCollectionVersions).mockImplementation(async (_id, before) =>
    Array.from({ length: before ? 2 : 11 }, (_, index) => ({
      id: `history-${before ?? 20}-${index}`,
      version: (before ? before - 1 : 20) - index,
      snapshot_json: { name: "Past list", member_entity_ids: [], visibility: "private" },
      changed_by_user_id: "owner",
      created_at: first.created_at,
    })),
  );
  setup(first.id);
  const summary = await screen.findByText("列表变更历史");
  expect(listCollectionVersions).not.toHaveBeenCalled();
  const details = summary.closest("details");
  if (!details) throw new Error("History disclosure missing");
  details.open = true;
  fireEvent(details, new Event("toggle"));
  await screen.findByText("v20");
  expect(screen.queryByText("v10")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "读取更早版本" }));
  await waitFor(() => expect(listCollectionVersions).toHaveBeenCalledWith(first.id, 11, expect.any(AbortSignal)));
  await screen.findByText("v10");
});

it("searches and pages the catalog without changing the open detail", async () => {
  vi.mocked(loadCollectionCatalog).mockResolvedValue({ items: [first, second], total: 70, limit: 25, offset: 0 });
  const result = setup(first.id);
  await screen.findByRole("navigation", { name: "列表目录分页" });
  fireEvent.click(screen.getByRole("button", { name: "列表目录下一页" }));
  await waitFor(() => expect(loadCollectionCatalog).toHaveBeenCalledWith("", 25, expect.any(AbortSignal)));
  fireEvent.change(screen.getByLabelText("搜索列表名称或说明"), { target: { value: "  Clinical  " } });
  fireEvent.click(screen.getByRole("button", { name: "筛选列表" }));
  await waitFor(() => expect(loadCollectionCatalog).toHaveBeenCalledWith("Clinical", 0, expect.any(AbortSignal)));
  expect(result.navigate).not.toHaveBeenCalled();
});
