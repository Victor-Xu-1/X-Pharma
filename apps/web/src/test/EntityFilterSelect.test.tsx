import { fireEvent, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";

import { EntityFilterSelect } from "../components/EntityFilterSelect";
import { getEntity, lookupEntities, lookupEntityTypes } from "../lib/contracts/intelligence";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/intelligence", () => ({
  intelligenceKeys: {
    lookup: (query: string, entityType: string) => ["lookup", query, entityType],
    lookupMany: (query: string, entityTypes: readonly string[]) => ["lookup-many", query, entityTypes],
    entity: (entityId: string) => ["entity", entityId],
  },
  lookupEntities: vi.fn(),
  lookupEntityTypes: vi.fn(),
  getEntity: vi.fn(),
}));

const target = {
  id: "target-1",
  canonical_entity_id: "target-1",
  entity_type: "target" as const,
  name: "EGFR",
  description: null,
  external_ids: { HGNC: "3236" },
  aliases: ["ERBB1"],
  attributes: { english_name: "Epidermal growth factor receptor" },
  match: {
    match_type: "alias" as const,
    match_relation: "exact" as const,
    matched_value: "ERBB1",
    namespace: null,
  },
  review_status: "verified" as const,
  created_at: "2026-07-24T00:00:00Z",
  updated_at: "2026-07-24T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(lookupEntities).mockResolvedValue([target]);
  vi.mocked(lookupEntityTypes).mockResolvedValue([target]);
  vi.mocked(getEntity).mockResolvedValue(target);
});

it.each(["", "x", "unresolved"])(
  "never submits an unresolved candidate input, including closed or short query %j",
  (query) => {
    const onChange = vi.fn();
    renderWithQueryClient(
      <EntityFilterSelect
        label="关联实体"
        entityType="target"
        value=""
        onChange={onChange}
        placeholder="输入关联实体"
      />,
    );
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: query } });
    if (query.length >= 2) fireEvent.keyDown(input, { key: "Escape" });
    expect(fireEvent.keyDown(input, { key: "Enter" })).toBe(false);
    expect(onChange).not.toHaveBeenCalled();
  },
);

it("searches and restores one stable entity across multiple governed types", async () => {
  const onChange = vi.fn();
  renderWithQueryClient(
    <EntityFilterSelect
      label="关联实体"
      entityType={["drug", "target", "disease", "organization"]}
      value=""
      onChange={onChange}
      placeholder="输入关联实体"
    />,
  );

  fireEvent.change(screen.getByLabelText("关联实体筛选"), { target: { value: "EGFR" } });
  const option = await screen.findByRole("option", { name: /EGFR/ });
  expect(lookupEntityTypes).toHaveBeenCalledWith(
    "EGFR",
    ["drug", "target", "disease", "organization"],
    expect.any(AbortSignal),
  );
  fireEvent.click(option);
  expect(onChange).toHaveBeenCalledWith("target-1", "EGFR");
});

it("selects a stable governed entity id and clears it", async () => {
  const onChange = vi.fn();
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="" onChange={onChange} placeholder="输入靶点" />,
  );

  fireEvent.change(screen.getByLabelText("靶点筛选"), { target: { value: "EGFR" } });
  const option = await screen.findByRole("option", { name: /EGFR/ });
  expect(option).toHaveTextContent("HGNC · 3236");
  expect(option).toHaveTextContent("别名精确匹配：ERBB1");
  expect(option).not.toHaveTextContent("别名：ERBB1");
  expect(option).toHaveTextContent("英文名 Epidermal growth factor receptor");
  expect(option).not.toHaveTextContent("规范");
  expect(option).not.toHaveTextContent("target");
  fireEvent.click(option);
  expect(onChange).toHaveBeenCalledWith("target-1", "EGFR");

  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="target-1" onChange={onChange} placeholder="输入靶点" />,
  );
  expect(await screen.findByText("EGFR")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "清除靶点" }));
  expect(onChange).toHaveBeenCalledWith("");
});

it("does not repeat the primary name as match detail or alias", async () => {
  vi.mocked(lookupEntities).mockResolvedValue([
    {
      ...target,
      name: "EGFR amplification",
      aliases: ["EGFR amplification"],
      external_ids: {},
      match: {
        match_type: "canonical_name",
        match_relation: "partial",
        matched_value: "EGFR amplification",
        namespace: null,
      },
    },
  ]);
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="" onChange={vi.fn()} placeholder="输入靶点" />,
  );

  fireEvent.change(screen.getByLabelText("靶点筛选"), { target: { value: "EGFR" } });
  const option = await screen.findByRole("option", { name: /EGFR amplification/ });
  expect(option).toHaveTextContent("EGFR amplification靶点");
  expect(option).not.toHaveTextContent("名称部分匹配");
  expect(option).not.toHaveTextContent("别名：");
});

it("supports keyboard disambiguation without moving focus out of the combobox", async () => {
  const secondTarget = {
    ...target,
    id: "target-2",
    canonical_entity_id: "target-2",
    name: "EGFR T790M",
    external_ids: { HGNC: "3236-T790M" },
    aliases: ["ERBB1 T790M"],
  };
  vi.mocked(lookupEntities).mockResolvedValue([target, secondTarget]);
  const onChange = vi.fn();
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="" onChange={onChange} placeholder="输入靶点" />,
  );

  const input = screen.getByRole("combobox", { name: "靶点筛选" });
  input.focus();
  fireEvent.change(input, { target: { value: "EGFR" } });
  const options = await screen.findAllByRole("option");

  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(input).toHaveFocus();
  expect(input).toHaveAttribute("aria-activedescendant", options[0].id);
  expect(options[0]).toHaveAttribute("aria-selected", "true");

  fireEvent.keyDown(input, { key: "ArrowDown" });
  expect(input).toHaveAttribute("aria-activedescendant", options[1].id);
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onChange).toHaveBeenCalledWith("target-2", "EGFR T790M");
});

it("closes the candidate list with Escape and gives repeated entity types unique aria relationships", async () => {
  renderWithQueryClient(
    <>
      <EntityFilterSelect label="主靶点" entityType="target" value="" onChange={vi.fn()} placeholder="输入主靶点" />
      <EntityFilterSelect label="联用靶点" entityType="target" value="" onChange={vi.fn()} placeholder="输入联用靶点" />
    </>,
  );

  const [primary, combination] = screen.getAllByRole("combobox");
  expect(primary.getAttribute("aria-controls")).toBeTruthy();
  expect(combination.getAttribute("aria-controls")).toBeTruthy();
  expect(primary.getAttribute("aria-controls")).not.toBe(combination.getAttribute("aria-controls"));

  fireEvent.change(primary, { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR/ });
  expect(primary).toHaveAttribute("aria-expanded", "true");
  fireEvent.keyDown(primary, { key: "Escape" });
  expect(primary).toHaveAttribute("aria-expanded", "false");
  expect(primary).not.toHaveAttribute("aria-activedescendant");
});

it("does not present a mismatched entity type as a valid selection", async () => {
  vi.mocked(getEntity).mockResolvedValue({ ...target, entity_type: "drug" });
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="target-1" onChange={vi.fn()} placeholder="输入靶点" />,
  );
  expect(await screen.findByText("所选实体不可用")).toBeInTheDocument();
});

it("uses public-facing language for the selector and empty result", async () => {
  vi.mocked(lookupEntities).mockResolvedValue([]);
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="" onChange={vi.fn()} placeholder="输入靶点" />,
  );

  const group = screen.getByRole("group", { name: "靶点检索与选择" });
  fireEvent.change(screen.getByRole("combobox", { name: "靶点筛选" }), { target: { value: "missing" } });

  expect(await screen.findByText("未找到匹配项")).toBeInTheDocument();
  expect(group).not.toHaveTextContent("规范实体");
});

it.each(["ALK", "E"])("never offers candidates for the previous query while typing %s", async (nextQuery) => {
  const onChange = vi.fn();
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="" onChange={onChange} placeholder="输入靶点" />,
  );
  const input = screen.getByRole("combobox", { name: "靶点筛选" });
  fireEvent.change(input, { target: { value: "EGFR" } });
  await screen.findByRole("option", { name: /EGFR/ });
  fireEvent.change(input, { target: { value: nextQuery } });
  expect(screen.queryByRole("option", { name: /EGFR/ })).not.toBeInTheDocument();
  expect(input).not.toHaveAttribute("aria-activedescendant");
  fireEvent.keyDown(input, { key: "ArrowDown" });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(onChange).not.toHaveBeenCalled();
});

it("offers an explicit bounded retry when the candidate lookup fails", async () => {
  vi.mocked(lookupEntities).mockRejectedValueOnce(new Error("lookup unavailable"));
  const onChange = vi.fn();
  renderWithQueryClient(
    <EntityFilterSelect label="靶点" entityType="target" value="" onChange={onChange} placeholder="输入靶点" />,
  );
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "EGFR" } });
  const retry = await screen.findByRole("button", { name: "重试靶点候选检索" });
  expect(screen.queryByRole("option")).not.toBeInTheDocument();
  expect(onChange).not.toHaveBeenCalled();
  retry.focus();
  fireEvent.click(retry);
  expect(screen.getByRole("combobox")).toHaveFocus();
  await screen.findByRole("option", { name: /EGFR/ });
  await waitFor(() => expect(lookupEntities).toHaveBeenCalledTimes(2));
});

it("closes only the candidate popup on the first Escape", async () => {
  const parentKey = vi.fn();
  renderWithQueryClient(
    <div role="dialog" aria-label="父弹窗" tabIndex={-1} onKeyDown={parentKey}>
      <EntityFilterSelect label="靶点" entityType="target" value="" onChange={vi.fn()} placeholder="输入靶点" />
    </div>,
  );
  const input = screen.getByRole("combobox");
  fireEvent.change(input, { target: { value: "EGFR" } });
  await screen.findByRole("option");
  fireEvent.keyDown(input, { key: "Escape" });
  expect(screen.queryByRole("option")).not.toBeInTheDocument();
  expect(parentKey).not.toHaveBeenCalled();
  fireEvent.keyDown(input, { key: "Escape" });
  expect(parentKey).toHaveBeenCalledOnce();
});
