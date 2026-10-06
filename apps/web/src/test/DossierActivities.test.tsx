import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import type { EntityDossier } from "../lib/contracts/entityDossier";
import type { BioactivityRead, EntityRead } from "../lib/generated";
import { Activities } from "../views/EntityDossierView";

function entity(id: string, name: string, entityType: "drug" | "target"): EntityRead {
  return {
    id,
    canonical_entity_id: id,
    name,
    entity_type: entityType,
    description: null,
    attributes: {},
    external_ids: {},
    review_status: "verified",
    created_at: "2026-10-04T00:00:00Z",
    updated_at: "2026-10-04T00:00:00Z",
  };
}

function dossier(overrides: Partial<BioactivityRead> = {}): EntityDossier {
  return {
    entity: entity("drug-1", "Compound A", "drug"),
    relationships: [
      {
        id: "relationship-1",
        predicate: "has_target",
        direction: "outgoing",
        related_entity: entity("target-1", "EGFR", "target"),
        attributes: {},
        review_status: "verified",
        valid_from: null,
        valid_to: null,
      },
    ],
    activities: [
      {
        id: "activity-1",
        assay_id: "assay-1",
        compound_entity_id: "drug-1",
        target_entity_id: "target-1",
        source_system: "chembl",
        source_activity_id: "reported-1",
        reported_type: "IC50",
        reported_relation: "=",
        reported_value: "50",
        reported_units: "nM",
        standard_type: "IC50",
        standard_relation: "=",
        standard_value: 0.05,
        standard_units: "µM",
        pchembl_value: null,
        ...overrides,
      },
    ],
    programs: [],
    clinical_trials: [],
    patents: [],
    deals: [],
    regulatory_events: [],
    news_events: [],
    structures: [],
    target_evidence: [],
    coverage: [],
    as_of: "2026-10-04T00:00:00Z",
  };
}

it("uses authorized dossier names and separates reported from aligned standard values", () => {
  render(<Activities data={dossier()} onOpen={vi.fn()} />);
  const table = screen.getByRole("table", { name: "关联活性数据" });
  expect(within(table).getByRole("cell", { name: "Compound A" })).toBeInTheDocument();
  expect(within(table).getByRole("cell", { name: "EGFR" })).toBeInTheDocument();
  expect(within(table).getByRole("columnheader", { name: "来源报告值" })).toBeInTheDocument();
  expect(within(table).getByRole("columnheader", { name: "对齐标准值" })).toBeInTheDocument();
  expect(within(table).getByRole("cell", { name: "= 50 nM" })).toBeInTheDocument();
  expect(within(table).getByRole("cell", { name: "= 0.05 µM" })).toBeInTheDocument();
  expect(within(table).getByRole("cell", { name: "ChEMBL" })).toBeInTheDocument();
});

it("never substitutes an unaligned reported measurement into the standard-value column", () => {
  render(
    <Activities
      data={dossier({
        compound_entity_id: "unloaded-id",
        target_entity_id: null,
        reported_relation: ">",
        standard_type: null,
        standard_relation: null,
        standard_value: null,
        standard_units: null,
      })}
      onOpen={vi.fn()}
    />,
  );
  expect(screen.getByRole("cell", { name: "> 50 nM" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "无对齐标准值" })).toBeInTheDocument();
  expect(screen.getByText("名称未加载")).toHaveAttribute("title", "unloaded-id");
  expect(screen.getByRole("cell", { name: "未披露" })).toBeInTheDocument();
  expect(screen.queryByText("unloaded-id")).not.toBeInTheDocument();
});

it("retains zero values and shows pChEMBL only when a value was actually provided", () => {
  const { rerender } = render(<Activities data={dossier()} onOpen={vi.fn()} />);
  expect(screen.queryByRole("columnheader", { name: "pChEMBL" })).not.toBeInTheDocument();
  rerender(
    <Activities data={dossier({ standard_value: 0, standard_units: "nM", pchembl_value: 0 })} onOpen={vi.fn()} />,
  );
  expect(screen.getByRole("cell", { name: "= 0 nM" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "pChEMBL" })).toBeInTheDocument();
  expect(screen.getByRole("cell", { name: "0" })).toBeInTheDocument();
});

it("keeps provenance actions attached to the original activity identity", () => {
  const onOpen = vi.fn();
  render(<Activities data={dossier()} onOpen={onOpen} />);
  fireEvent.click(screen.getByRole("button", { name: "查看 活性记录 的原始证据" }));
  expect(onOpen).toHaveBeenCalledWith({
    resourceType: "activity_measurement",
    resourceId: "activity-1",
    label: "活性记录",
  });
});
