import { beforeEach, expect, it } from "vitest";

import {
  currentDomainExportQuery,
  defaultWorkspacePolicyFields,
  domainExportCatalog,
} from "../lib/contracts/domainExports";

beforeEach(() => {
  window.history.replaceState({}, "", "/workspace/research");
});

it("keeps only each dataset's versioned server query fields", () => {
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=regulatory&q=EGFR&agency=FDA&offset=40&display=timeline&unknown=secret",
  );

  expect(currentDomainExportQuery("regulatory")).toEqual({ q: "EGFR", agency: "FDA" });
});

it("preserves canonical multi-type entity filters for governed exports", () => {
  window.history.replaceState({}, "", "/workspace/research?view=explorer&q=EGFR&types=drug,target,unknown");

  expect(currentDomainExportQuery("entities")).toEqual({
    q: "EGFR",
    entity_types: ["drug", "target"],
    review_status: "verified",
  });
});

it("exports the published research result set even when an obsolete URL requests drafts", () => {
  window.history.replaceState({}, "", "/workspace/research?view=explorer&q=EGFR&review_status=draft");
  expect(currentDomainExportQuery("entities")).toEqual({ q: "EGFR", review_status: "verified" });
});

it("preserves repeated normalized trial entities for governed exports", () => {
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=trials" +
      "&role_entity_ids=550e8400-e29b-41d4-a716-446655440003" +
      "&role_entity_ids=550e8400-e29b-41d4-a716-446655440004" +
      "&investigational_drug_entity_ids=550e8400-e29b-41d4-a716-446655440010" +
      "&combination_drug_entity_ids=550e8400-e29b-41d4-a716-446655440011" +
      "&investigational_target_entity_ids=550e8400-e29b-41d4-a716-446655440012" +
      "&combination_target_entity_ids=550e8400-e29b-41d4-a716-446655440013" +
      "&linked_drug_modality=antibody&linked_drug_modality=small%20molecule" +
      "&linked_drug_innovation_type=innovative&linked_drug_category=biologic" +
      "&linked_drug_program_tag=first_in_class&linked_drug_global_phase=phase_3" +
      "&linked_drug_organization_country_region=CN" +
      "&role_entity_role=investigational_drug",
  );

  expect(currentDomainExportQuery("trials")).toEqual({
    role_entity_ids: ["550e8400-e29b-41d4-a716-446655440003", "550e8400-e29b-41d4-a716-446655440004"],
    investigational_drug_entity_ids: ["550e8400-e29b-41d4-a716-446655440010"],
    combination_drug_entity_ids: ["550e8400-e29b-41d4-a716-446655440011"],
    investigational_target_entity_ids: ["550e8400-e29b-41d4-a716-446655440012"],
    combination_target_entity_ids: ["550e8400-e29b-41d4-a716-446655440013"],
    linked_drug_modality: ["antibody", "small molecule"],
    linked_drug_innovation_type: ["innovative"],
    linked_drug_category: ["biologic"],
    linked_drug_program_tag: ["first_in_class"],
    linked_drug_global_phase: "phase_3",
    linked_drug_organization_country_region: "CN",
    role_entity_role: "investigational_drug",
  });
});

it("preserves ordered repeated sorting for governed exports", () => {
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=trials&q=EGFR&sort=overall_status%3Aasc&sort=registry_id%3Adesc",
  );

  expect(currentDomainExportQuery("trials")).toEqual({
    q: "EGFR",
    sort: ["overall_status:asc", "registry_id:desc"],
  });
});

it("preserves governed pipeline organization relationship filters for exports", () => {
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=pipeline&program_status=active&organization_role=collaborator" +
      "&organization_type=biotech&organization_country_region=US&display=landscape&offset=100",
  );

  expect(currentDomainExportQuery("pipelines")).toEqual({
    program_status: "active",
    organization_role: "collaborator",
    organization_type: "biotech",
    organization_country_region: "US",
  });
});

it("carries deal asset and canonical entity filters into the governed export query", () => {
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=deals&q=EGFR" +
      "&asset_entity_id=550e8400-e29b-41d4-a716-446655440021" +
      "&target_entity_id=550e8400-e29b-41d4-a716-446655440022" +
      "&disease_entity_id=550e8400-e29b-41d4-a716-446655440023" +
      "&asset_modality=antibody" +
      "&asset_program_tag=first_in_class&asset_program_tag=new_modality" +
      "&display=landscape&offset=20",
  );

  expect(currentDomainExportQuery("deals")).toEqual({
    q: "EGFR",
    asset_entity_id: "550e8400-e29b-41d4-a716-446655440021",
    target_entity_id: "550e8400-e29b-41d4-a716-446655440022",
    disease_entity_id: "550e8400-e29b-41d4-a716-446655440023",
    asset_modality: ["antibody"],
    asset_program_tag: ["first_in_class", "new_modality"],
  });
});

it("carries the canonical epidemiology disease filter into the governed export query", () => {
  window.history.replaceState(
    {},
    "",
    "/workspace/research?view=epidemiology&measure=prevalence" +
      "&disease_entity_id=550e8400-e29b-41d4-a716-446655440031",
  );

  expect(currentDomainExportQuery("epidemiology")).toEqual({
    measure: "prevalence",
    disease_entity_id: "550e8400-e29b-41d4-a716-446655440031",
  });
});

it("defines stable id fields and unique qualified policy names for all eight datasets", () => {
  expect(Object.keys(domainExportCatalog)).toHaveLength(8);
  for (const config of Object.values(domainExportCatalog)) {
    expect(config.fields[0]?.value).toBe("id");
  }
  expect(new Set(defaultWorkspacePolicyFields).size).toBe(defaultWorkspacePolicyFields.length);
  expect(defaultWorkspacePolicyFields).toContain("entities.id");
  expect(defaultWorkspacePolicyFields).toContain("news.id");
});
