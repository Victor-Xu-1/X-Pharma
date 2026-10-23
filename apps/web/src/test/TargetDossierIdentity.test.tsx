import { act, fireEvent, screen } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { searchPipelines } from "../lib/contracts/pipeline";
import { loadTargetDossier, type TargetDossier } from "../lib/contracts/target";
import type { EntityRead } from "../lib/generated";
import { setLocale } from "../lib/i18n";
import type { Entity } from "../lib/types";
import type { TargetDossierSection } from "../lib/workspaceRouting";
import { TargetView } from "../views/TargetView";
import { renderWithQueryClient } from "./renderWithQueryClient";

vi.mock("../lib/contracts/target", async (original) => ({
  ...(await original<typeof import("../lib/contracts/target")>()),
  loadTargetDossier: vi.fn(),
}));
vi.mock("../lib/contracts/pipeline", async (original) => ({
  ...(await original<typeof import("../lib/contracts/pipeline")>()),
  searchPipelines: vi.fn(),
}));

// Typed, empty controlled fixture: not an ingestion input or a real target record.
const target: EntityRead & Entity = {
  id: "00000000-0000-4000-a000-000000000001",
  entity_type: "target",
  name: "Controlled target / 原始测试名称",
  description: "Controlled response boundary",
  external_ids: {},
  attributes: {},
  review_status: "verified",
  canonical_entity_id: "00000000-0000-4000-a000-000000000001",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
};
function dossier(): TargetDossier {
  return {
    entity: target,
    profile: { entity: target, activity_count: 0, program_count: 0, as_of: "2026-10-01T00:00:00Z" },
    as_of: "2026-10-01T00:00:00Z",
    summary: {
      program_count: 0,
      clinical_trial_count: 0,
      patent_count: 0,
      regulatory_event_count: 0,
      recruiting_trial_count: 0,
      unclassified_trial_status_count: 0,
      active_patent_count: 0,
      unclassified_patent_status_count: 0,
      approval_event_count: 0,
      status_vocabulary_version: "controlled-test",
    },
    activities: [],
    clinical_trials: [],
    coverage: [],
    deals: [],
    news_events: [],
    patents: [],
    programs: [],
    regulatory_events: [],
    relationships: [],
    structures: [],
    target_evidence: [],
  };
}
function renderTarget(entity: Entity = target, activeSection: TargetDossierSection = "overview") {
  const onSectionChange = vi.fn();
  const result = renderWithQueryClient(
    <TargetView
      target={entity}
      activeSection={activeSection}
      onSectionChange={onSectionChange}
      onOpenEntity={vi.fn()}
      onOpenTrial={vi.fn()}
      onOpenPatent={vi.fn()}
      onOpenDeal={vi.fn()}
      onOpenRegulatoryEvent={vi.fn()}
      onOpenNewsEvent={vi.fn()}
    />,
  );
  return { ...result, onSectionChange };
}

beforeEach(() => {
  vi.clearAllMocks();
  setLocale("en");
  vi.mocked(loadTargetDossier).mockResolvedValue(dossier());
  vi.mocked(searchPipelines).mockImplementation(() => new Promise(() => {}));
});

for (const locale of ["en", "zh-CN"] as const) {
  for (const owner of ["entity", "profile"] as const) {
    for (const mismatch of ["id", "type"] as const) {
      it(`rejects ${owner} ${mismatch} mismatch before downstream pipeline work in ${locale}`, async () => {
        setLocale(locale);
        const response = dossier();
        const foreign: EntityRead & Entity = {
          ...target,
          name: "FOREIGN SCIENTIFIC IDENTITY",
          id: mismatch === "id" ? "00000000-0000-4000-b000-000000000002" : target.id,
          entity_type: mismatch === "type" ? "drug" : "target",
        };
        if (owner === "entity") response.entity = foreign;
        else response.profile = { ...response.profile, entity: foreign };
        vi.mocked(loadTargetDossier).mockResolvedValue(response);
        const { onSectionChange } = renderTarget(target, "pipeline");
        expect(
          await screen.findByText(
            locale === "en" ? "Target dossier does not match the requested identity" : "靶点档案与请求实体不一致",
          ),
        ).toBeVisible();
        expect(screen.queryByText("FOREIGN SCIENTIFIC IDENTITY")).not.toBeInTheDocument();
        expect(document.querySelector(".target-dossier-header")).toBeNull();
        expect(searchPipelines).not.toHaveBeenCalled();
        expect(onSectionChange).not.toHaveBeenCalled();
        expect(screen.getByRole("button", { name: locale === "en" ? "Retry" : "重试" })).toBeEnabled();
      });
    }
  }
  it(`rejects a non-target request without starting a target read in ${locale}`, async () => {
    setLocale(locale);
    renderTarget({ ...target, entity_type: "drug" });
    expect(
      await screen.findByText(
        locale === "en" ? "This link is not a target entity" : "该深链接不是靶点实体，无法打开靶点档案",
      ),
    ).toBeVisible();
    expect(loadTargetDossier).not.toHaveBeenCalled();
    expect(searchPipelines).not.toHaveBeenCalled();
  });
  it(`preserves a valid raw scientific identity in ${locale}`, async () => {
    setLocale(locale);
    renderTarget();
    expect(await screen.findByRole("heading", { name: target.name })).toBeVisible();
    expect(screen.queryByRole("button", { name: locale === "en" ? "Retry" : "重试" })).not.toBeInTheDocument();
    expect(loadTargetDossier).toHaveBeenCalledTimes(1);
  });
}

it("recovers only by explicit refetch and retains the original scientific name across language changes", async () => {
  const response = dossier();
  vi.mocked(loadTargetDossier).mockResolvedValueOnce({
    ...response,
    profile: { ...response.profile, entity: { ...target, id: "foreign-target" } },
  });
  renderTarget();
  await screen.findByText("Target dossier does not match the requested identity");
  fireEvent.click(screen.getByRole("button", { name: "Retry" }));
  expect(await screen.findByRole("heading", { name: target.name })).toBeVisible();
  expect(loadTargetDossier).toHaveBeenCalledTimes(2);
  act(() => setLocale("zh-CN"));
  expect(screen.getByRole("heading", { name: target.name })).toBeVisible();
  expect(loadTargetDossier).toHaveBeenCalledTimes(2);
});
