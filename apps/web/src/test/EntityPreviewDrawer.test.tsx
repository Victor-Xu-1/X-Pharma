import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { EntityPreviewDrawer } from "../components/EntityPreviewDrawer";
import { setLocale } from "../lib/i18n";
import type { Entity } from "../lib/types";

const entity: Entity = {
  id: "drug-1",
  name: "OSIMERTINIB",
  aliases: ["OSIMERTINIB", "AZD9291", "Tagrisso"],
  entity_type: "drug",
  description: null,
  external_ids: { chembl: "CHEMBL3353410" },
  attributes: {},
  review_status: "verified",
  created_at: "2026-10-07T00:00:00Z",
  updated_at: "2026-10-07T00:00:00Z",
};

it("shows source-reported research codes in the preview without repeating the canonical name", () => {
  render(
    <EntityPreviewDrawer
      active
      entity={entity}
      invalidId={false}
      loading={false}
      error=""
      onClose={vi.fn()}
      onOpenEntity={vi.fn()}
    />,
  );
  expect(screen.getByRole("region", { name: "别名与研发代号" })).toBeVisible();
  expect(screen.getByText("AZD9291")).toBeVisible();
  expect(screen.getByText("Tagrisso")).toBeVisible();
  expect(screen.getAllByText("OSIMERTINIB")).toHaveLength(1);
});

it("switches preview labels and preserves raw source attributes and close behavior", () => {
  const sourceEntity = {
    ...entity,
    description: "来源原文：中文试验",
    attributes: { mechanism: "原文作用机制", source_secret: "hidden" },
  };
  const onClose = vi.fn();
  const props = {
    active: true,
    entity: sourceEntity,
    invalidId: false,
    loading: false,
    error: "",
    onClose,
    onOpenEntity: vi.fn(),
  };
  const { rerender } = render(<EntityPreviewDrawer {...props} />);
  setLocale("en");
  rerender(<EntityPreviewDrawer {...props} />);
  expect(screen.getByRole("heading", { name: "Entity summary" })).toBeVisible();
  expect(screen.getByText("Mechanism of action")).toBeVisible();
  expect(screen.getByText("原文作用机制")).toBeVisible();
  expect(screen.getByText("来源原文：中文试验")).toBeVisible();
  expect(screen.queryByText("hidden")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Open dossier" })).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "Close entity preview" }));
  expect(onClose).toHaveBeenCalledTimes(1);
});
