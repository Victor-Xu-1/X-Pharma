import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { EntityPreviewDrawer } from "../components/EntityPreviewDrawer";
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
