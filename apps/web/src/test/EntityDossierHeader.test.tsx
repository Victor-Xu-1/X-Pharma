import { act, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import type { EntityDossier } from "../lib/contracts/entityDossier";
import { setLocale } from "../lib/i18n";
import { EntityDossierHeader } from "../views/dossier/EntityDossierHeader";
import { dossier } from "./fixtures/companyDossier";
import { renderWithQueryClient } from "./renderWithQueryClient";

// Presentation fixture only; no scientific records or host/service writes.
const name = "Controlled long clinical protocol — preserve every word, identifier and source-owned scientific term";
const data: Pick<EntityDossier, "entity" | "coverage" | "relationships" | "as_of"> = {
  entity: { ...dossier.entity, entity_type: "clinical_trial", name, aliases: ["RAW-CODE-001", "原始研究代号"] },
  coverage: [
    { domain: "clinical_trials", total: 101, returned: 1, status: "available", note: "Controlled source note" },
  ],
  relationships: [],
  as_of: "2026-10-01T10:00:00Z",
};
beforeEach(() => setLocale("en"));

it("retains the complete raw title and aliases rather than a shortened presentation copy", () => {
  renderWithQueryClient(<EntityDossierHeader data={data} />);
  expect(screen.getByRole("heading", { name })).toHaveTextContent(name);
  expect(screen.getByText("RAW-CODE-001")).toBeVisible();
  expect(screen.getByText("原始研究代号")).toBeVisible();
});

it("uses complete server coverage totals rather than truncated returned collections", () => {
  renderWithQueryClient(<EntityDossierHeader data={data} />);
  const fields = document.querySelectorAll(".entity-dossier-metrics > div");
  expect(fields).toHaveLength(4);
  expect(fields[0]?.querySelector("dd")).toHaveTextContent("101");
  expect(fields[1]?.querySelector("dd")).toHaveTextContent("1 / 1");
  expect(fields[2]?.querySelector("dd")).toHaveTextContent("0");
  expect(fields[3]?.querySelector("dd")).toHaveAttribute(
    "title",
    "Dossier query time, not the last update of every source",
  );
});

it("changes only interface captions across languages and retains source identity and all metrics", () => {
  renderWithQueryClient(<EntityDossierHeader data={data} />);
  expect(screen.getByText("Linked records")).toBeVisible();
  act(() => setLocale("zh-CN"));
  expect(screen.getByText("关联记录")).toBeVisible();
  expect(screen.getByRole("heading", { name })).toHaveTextContent(name);
  expect(screen.getByText("RAW-CODE-001")).toBeVisible();
  expect(screen.getByText("101")).toBeVisible();
});
