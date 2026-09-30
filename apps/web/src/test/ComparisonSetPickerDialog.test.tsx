import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import { ComparisonSetPickerDialog } from "../components/ComparisonSetPickerDialog";

it("lets a user create a comparison list without losing selected entities", () => {
  const onCreateSet = vi.fn().mockResolvedValue(undefined);

  render(
    <ComparisonSetPickerDialog
      open
      selectedCount={2}
      sets={[]}
      selectedSetId=""
      loading={false}
      pending={false}
      error=""
      onSetChange={vi.fn()}
      onClose={vi.fn()}
      onSubmit={vi.fn()}
      onCreateSet={onCreateSet}
    />,
  );

  expect(
    screen.getByText("当前没有可编辑的对比列表。直接创建一个新列表，已选择的实体会继续加入其中。"),
  ).toBeInTheDocument();
  const createButton = screen.getByRole("button", { name: "创建并加入" });
  expect(createButton).toBeDisabled();

  fireEvent.change(screen.getByLabelText("新建列表"), { target: { value: "EGFR 竞品对比" } });
  fireEvent.click(screen.getByRole("checkbox", { name: "与团队共享" }));
  expect(createButton).not.toBeDisabled();

  fireEvent.click(createButton);
  expect(onCreateSet).toHaveBeenCalledWith("EGFR 竞品对比", "tenant");
});

it("creates the list when the user submits the new-list field with Enter", () => {
  const onCreateSet = vi.fn().mockResolvedValue(undefined);

  render(
    <ComparisonSetPickerDialog
      open
      selectedCount={1}
      sets={[]}
      selectedSetId=""
      loading={false}
      pending={false}
      error=""
      onSetChange={vi.fn()}
      onClose={vi.fn()}
      onSubmit={vi.fn()}
      onCreateSet={onCreateSet}
    />,
  );

  const nameInput = screen.getByLabelText("新建列表");
  fireEvent.change(nameInput, { target: { value: "EGFR 快速对比" } });
  fireEvent.submit(nameInput.closest("form") as HTMLFormElement);

  expect(onCreateSet).toHaveBeenCalledWith("EGFR 快速对比", "private");
});

it("keeps the existing-list submit path when an editable list is available", () => {
  const onSubmit = vi.fn();
  const existingSet = {
    created_at: "2026-08-10T00:00:00Z",
    description: "",
    editable: true,
    id: "set-1",
    member_count: 1,
    name: "已有列表",
    owner_user_id: "user-1",
    updated_at: "2026-08-10T00:00:00Z",
    version: 2,
    visibility: "private" as const,
  };

  render(
    <ComparisonSetPickerDialog
      open
      selectedCount={1}
      sets={[existingSet]}
      selectedSetId="set-1"
      loading={false}
      pending={false}
      error=""
      onSetChange={vi.fn()}
      onClose={vi.fn()}
      onSubmit={onSubmit}
    />,
  );

  fireEvent.submit(screen.getByRole("dialog"));
  expect(onSubmit).toHaveBeenCalledTimes(1);
});

it("does not submit a second create request while the first request is pending", () => {
  const onCreateSet = vi.fn(() => new Promise<void>(() => {}));

  render(
    <ComparisonSetPickerDialog
      open
      selectedCount={2}
      sets={[]}
      selectedSetId=""
      loading={false}
      pending
      error=""
      onSetChange={vi.fn()}
      onClose={vi.fn()}
      onSubmit={vi.fn()}
      onCreateSet={onCreateSet}
    />,
  );

  const nameInput = screen.getByLabelText("新建列表");
  fireEvent.change(nameInput, { target: { value: "EGFR 对比" } });
  fireEvent.submit(nameInput.closest("form") as HTMLFormElement);

  expect(onCreateSet).not.toHaveBeenCalled();
});
