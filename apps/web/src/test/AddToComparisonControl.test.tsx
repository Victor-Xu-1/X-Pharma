import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import {
  addComparisonSetMembers,
  type CollectionDetail,
  type CollectionEntity,
  getComparisonSet,
  listComparisonSets,
} from "../lib/contracts/collections";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/collections", () => ({
  collectionsKeys: {
    sets: ["collections", "sets"],
    detail: (id: string) => ["collections", "sets", id],
  },
  addComparisonSetMembers: vi.fn(),
  createComparisonSet: vi.fn(),
  getComparisonSet: vi.fn(),
  listComparisonSets: vi.fn(),
}));

const entityBase: CollectionEntity = {
  id: "drug-1",
  canonical_entity_id: "drug-1",
  entity_type: "drug",
  name: "Drug A",
  description: "EGFR inhibitor A",
  external_ids: {},
  attributes: {},
  review_status: "verified",
  created_at: "2026-08-10T00:00:00Z",
  updated_at: "2026-08-10T00:00:00Z",
};

const editableSet = {
  created_at: "2026-08-10T00:00:00Z",
  description: "",
  editable: true,
  id: "set-1",
  member_count: 0,
  name: "EGFR 竞品",
  owner_user_id: "user-1",
  updated_at: "2026-08-10T00:00:00Z",
  version: 1,
  visibility: "private" as const,
};

const addedDetail: CollectionDetail = {
  ...editableSet,
  member_count: 2,
  version: 2,
  members: [
    {
      id: "member-1",
      position: 0,
      added_by_user_id: "user-1",
      created_at: "2026-08-10T00:00:00Z",
      entity: entityBase,
    },
    {
      id: "member-2",
      position: 1,
      added_by_user_id: "user-1",
      created_at: "2026-08-10T00:00:00Z",
      entity: { ...entityBase, id: "drug-2", canonical_entity_id: "drug-2", name: "Drug B" },
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(listComparisonSets).mockResolvedValue([editableSet]);
  vi.mocked(getComparisonSet).mockResolvedValue({ ...editableSet, members: [] });
  vi.mocked(addComparisonSetMembers).mockResolvedValue(addedDetail);
});

it("offers the comparison list after selected drugs are added", async () => {
  const onComparisonReady = vi.fn();

  renderWithQueryClient(
    <AddToComparisonControl
      selectedEntityIds={["drug-1", "drug-2"]}
      onAdded={vi.fn()}
      onComparisonReady={onComparisonReady}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "加入列表（2）" }));
  await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
  await waitFor(() => expect(screen.getByRole("button", { name: "确认加入" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "确认加入" }));

  await waitFor(() => {
    expect(onComparisonReady).toHaveBeenCalledWith("set-1", ["drug-1", "drug-2"]);
  });
});

it("adds only new entities and explains which selected entities were already present", async () => {
  const existingDetail: CollectionDetail = {
    ...editableSet,
    member_count: 1,
    version: 4,
    members: [addedDetail.members[0]],
  };
  const updatedDetail: CollectionDetail = {
    ...existingDetail,
    member_count: 2,
    version: 5,
    members: addedDetail.members,
  };
  vi.mocked(listComparisonSets).mockResolvedValue([{ ...editableSet, member_count: 1, version: 4 }]);
  vi.mocked(getComparisonSet).mockResolvedValue(existingDetail);
  vi.mocked(addComparisonSetMembers).mockResolvedValue(updatedDetail);
  const onAdded = vi.fn();
  const onComparisonReady = vi.fn();

  renderWithQueryClient(
    <AddToComparisonControl
      selectedEntityIds={["drug-1", "drug-2"]}
      onAdded={onAdded}
      onComparisonReady={onComparisonReady}
    />,
  );

  fireEvent.click(screen.getByRole("button", { name: "加入列表（2）" }));
  expect(await screen.findByText("其中 1 个已在列表中，本次将新增 1 个")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "确认加入" }));

  await waitFor(() =>
    expect(addComparisonSetMembers).toHaveBeenCalledWith("set-1", {
      entity_ids: ["drug-2"],
      expected_version: 4,
    }),
  );
  expect(onAdded).toHaveBeenCalledWith("1 个实体已加入 EGFR 竞品，已跳过 1 个已存在实体");
  expect(onComparisonReady).toHaveBeenCalledWith("set-1", ["drug-1", "drug-2"]);
});

it("finishes without a duplicate write when every selected entity is already present", async () => {
  const existingDetail: CollectionDetail = {
    ...editableSet,
    member_count: 1,
    version: 4,
    members: [addedDetail.members[0]],
  };
  vi.mocked(listComparisonSets).mockResolvedValue([{ ...editableSet, member_count: 1, version: 4 }]);
  vi.mocked(getComparisonSet).mockResolvedValue(existingDetail);
  const onAdded = vi.fn();
  const onComparisonReady = vi.fn();

  renderWithQueryClient(
    <AddToComparisonControl selectedEntityIds={["drug-1"]} onAdded={onAdded} onComparisonReady={onComparisonReady} />,
  );

  fireEvent.click(screen.getByRole("button", { name: "加入列表（1）" }));
  expect(await screen.findByText("已选择的 1 个实体均已在列表中")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "完成" }));

  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(addComparisonSetMembers).not.toHaveBeenCalled();
  expect(onAdded).toHaveBeenCalledWith("所选实体均已在 EGFR 竞品 中，无需重复添加");
  expect(onComparisonReady).toHaveBeenCalledWith("set-1", ["drug-1"]);
});

it("keeps the picker open and translates a concurrent duplicate conflict", async () => {
  vi.mocked(addComparisonSetMembers).mockRejectedValueOnce(
    new Error("One or more entities are already in this comparison set"),
  );
  const onAdded = vi.fn();

  renderWithQueryClient(<AddToComparisonControl selectedEntityIds={["drug-1"]} onAdded={onAdded} />);

  fireEvent.click(screen.getByRole("button", { name: "加入列表（1）" }));
  await waitFor(() => expect(screen.getByRole("button", { name: "确认加入" })).toBeEnabled());
  fireEvent.click(screen.getByRole("button", { name: "确认加入" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("列表内容刚刚发生变化，请重新确认后再试");
  expect(screen.getByRole("dialog", { name: "加入对比列表" })).toBeVisible();
  expect(onAdded).not.toHaveBeenCalled();
});
