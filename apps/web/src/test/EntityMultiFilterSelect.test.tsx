import { fireEvent, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { EntityMultiFilterSelect } from "../components/EntityMultiFilterSelect";
import { getEntity, lookupEntities } from "../lib/contracts/intelligence";
import type { EntitySearchItemRead } from "../lib/generated";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/intelligence", () => ({
  intelligenceKeys: {
    lookup: (query: string, entityType: string) => ["lookup", query, entityType],
    entity: (entityId: string) => ["entity", entityId],
  },
  lookupEntities: vi.fn(),
  getEntity: vi.fn(),
}));

const originator: EntitySearchItemRead = {
  id: "550e8400-e29b-41d4-a716-446655440003",
  canonical_entity_id: "550e8400-e29b-41d4-a716-446655440003",
  entity_type: "drug",
  name: "VX-101",
  description: null,
  external_ids: { internal: "VX-101" },
  aliases: ["VX antibody"],
  attributes: { innovation_type: "First-in-class", modality: "单克隆抗体", drug_category: "生物制品" },
  match: {
    match_type: "alias",
    match_relation: "partial",
    matched_value: "VX antibody",
    namespace: null,
  },
  review_status: "verified",
  created_at: "2026-07-24T00:00:00Z",
  updated_at: "2026-07-24T00:00:00Z",
};
const biosimilar: EntitySearchItemRead = {
  ...originator,
  id: "550e8400-e29b-41d4-a716-446655440004",
  canonical_entity_id: "550e8400-e29b-41d4-a716-446655440004",
  name: "VX-101 Bio",
  external_ids: { internal: "VX-101-B" },
  aliases: ["VX biosimilar"],
};

beforeEach(() => {
  vi.mocked(lookupEntities).mockImplementation(async (query) =>
    query.toLowerCase().includes("bio") ? [biosimilar] : [originator],
  );
  vi.mocked(getEntity).mockImplementation(async (entityId) => {
    if (entityId === originator.id) return originator;
    if (entityId === biosimilar.id) return biosimilar;
    throw new Error("entity unavailable");
  });
});

it("selects, resolves and removes multiple stable entity ids", async () => {
  const onChange = vi.fn();
  const onResolved = vi.fn();
  function Harness() {
    const [values, setValues] = useState<string[]>([]);
    return (
      <EntityMultiFilterSelect
        label="关联规范药物（任一）"
        entityType="drug"
        values={values}
        onChange={(next, selectedId, selectedName) => {
          onChange(next, selectedId, selectedName);
          setValues(next);
        }}
        onResolved={onResolved}
        placeholder="输入规范药物"
      />
    );
  }
  renderWithQueryClient(<Harness />);

  fireEvent.change(screen.getByLabelText("关联规范药物（任一）筛选"), { target: { value: "VX" } });
  const originatorOption = await screen.findByRole("option", { name: /VX-101/ });
  expect(originatorOption).toHaveTextContent("药物");
  expect(originatorOption).toHaveTextContent("别名部分匹配：VX antibody");
  expect(originatorOption).toHaveTextContent("创新类型 First-in-class");
  expect(originatorOption).toHaveTextContent("药物类型 单克隆抗体");
  expect(originatorOption).toHaveTextContent("药品类别 生物制品");
  expect(originatorOption).not.toHaveTextContent("internal");
  fireEvent.click(originatorOption);
  expect(onChange).toHaveBeenLastCalledWith([originator.id], originator.id, originator.name);
  expect(await screen.findByText(originator.name)).toBeInTheDocument();

  fireEvent.change(screen.getByLabelText("关联规范药物（任一）筛选"), { target: { value: "Bio" } });
  fireEvent.click(await screen.findByRole("option", { name: /VX-101 Bio/ }));
  expect(onChange).toHaveBeenLastCalledWith([originator.id, biosimilar.id], biosimilar.id, biosimilar.name);
  await waitFor(() => expect(onResolved).toHaveBeenCalledWith(biosimilar.id, biosimilar.name));

  fireEvent.click(screen.getByRole("button", { name: `移除${originator.name}` }));
  expect(onChange).toHaveBeenLastCalledWith([biosimilar.id], undefined, undefined);
});

it("exposes invalid selections and a bounded selection limit", async () => {
  renderWithQueryClient(
    <EntityMultiFilterSelect
      label="关联规范药物（任一）"
      entityType="drug"
      values={[originator.id, "550e8400-e29b-41d4-a716-446655440099"]}
      onChange={vi.fn()}
      placeholder="输入规范药物"
      maxSelections={2}
    />,
  );

  expect(await screen.findByText("所选实体不可用")).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("已达到最多 2 项");
  expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
});

it("uses unique listbox relationships for multiple selectors of the same entity type", () => {
  renderWithQueryClient(
    <>
      <EntityMultiFilterSelect
        label="规范试验药物（任一）"
        entityType="drug"
        values={[]}
        onChange={vi.fn()}
        placeholder="输入试验药物"
      />
      <EntityMultiFilterSelect
        label="规范联用药物（任一）"
        entityType="drug"
        values={[]}
        onChange={vi.fn()}
        placeholder="输入联用药物"
      />
    </>,
  );

  const controls = screen.getAllByRole("combobox").map((input) => input.getAttribute("aria-controls"));
  expect(controls.every(Boolean)).toBe(true);
  expect(new Set(controls).size).toBe(2);
});

it("keeps focus in the multiselect combobox while keyboard-disambiguating a candidate", async () => {
  vi.mocked(lookupEntities).mockResolvedValue([originator, biosimilar]);
  const onChange = vi.fn();
  renderWithQueryClient(
    <EntityMultiFilterSelect
      label="规范试验药物（任一）"
      entityType="drug"
      values={[]}
      onChange={onChange}
      placeholder="输入试验药物"
    />,
  );

  const input = screen.getByRole("combobox", { name: "规范试验药物（任一）筛选" });
  input.focus();
  fireEvent.change(input, { target: { value: "VX" } });
  const options = await screen.findAllByRole("option");

  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute("aria-activedescendant", options[0].id);
  expect(options[0]).toHaveAttribute("aria-selected", "true");

  fireEvent.keyDown(input, { key: "End" });
  expect(input).toHaveAttribute("aria-activedescendant", options[1].id);
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onChange).toHaveBeenCalledWith([biosimilar.id], biosimilar.id, biosimilar.name);
  expect(input).toHaveAttribute("aria-expanded", "false");

  fireEvent.change(input, { target: { value: "VX" } });
  await screen.findAllByRole("option");
  fireEvent.keyDown(input, { key: "Escape" });
  expect(input).toHaveAttribute("aria-expanded", "false");
  expect(input).not.toHaveAttribute("aria-activedescendant");
});

it("uses public-facing language for the multiselect and empty result", async () => {
  vi.mocked(lookupEntities).mockResolvedValue([]);
  renderWithQueryClient(
    <EntityMultiFilterSelect
      label="试验药物（任一）"
      entityType="drug"
      values={[]}
      onChange={vi.fn()}
      placeholder="输入试验药物"
    />,
  );

  const group = screen.getByRole("group", { name: "试验药物（任一）多选" });
  fireEvent.change(screen.getByRole("combobox", { name: "试验药物（任一）筛选" }), {
    target: { value: "missing" },
  });

  expect(await screen.findByText("未找到可添加项")).toBeInTheDocument();
  expect(group).not.toHaveTextContent("规范实体");
});
