import type { CollectionDetail, CollectionEntity, CollectionPolicy } from "../../src/lib/contracts/collections";
import type { DrugComparison, EntityDossier } from "../../src/lib/contracts/entityDossier";
import type { ComparisonSetVersionRead } from "../../src/lib/generated";
import { targetLanguageFixture } from "./target-language";

/** Browser-only governed response shapes; no identities or scientific records are created. */
export function collectionLanguageFixture() {
  const target: CollectionEntity = targetLanguageFixture().entity;
  const company: CollectionEntity = {
    ...target,
    id: "550e8400-e29b-41d4-a716-446655440040",
    canonical_entity_id: "550e8400-e29b-41d4-a716-446655440040",
    entity_type: "organization",
    name: "原始登记申办方 / fixture",
    attributes: { identity_scope: "provider_label" },
    external_ids: {},
  };
  const drugs: CollectionEntity[] = [41, 42].map((id) => ({
    ...target,
    id: `550e8400-e29b-41d4-a716-4466554400${id}`,
    canonical_entity_id: `550e8400-e29b-41d4-a716-4466554400${id}`,
    entity_type: "drug",
    name: `Controlled drug ${id}`,
    external_ids: { chembl: `CHEMBL-FIXTURE-${id}` },
  }));
  const entities = [target, company, ...drugs];
  const detail: CollectionDetail = {
    id: "550e8400-e29b-41d4-a716-446655440030",
    owner_user_id: "controlled-list-user",
    name: "原始研究列表 / Controlled browser fixture",
    description: "原始业务说明 — not a real research deliverable",
    visibility: "private",
    version: 2,
    editable: true,
    member_count: entities.length,
    created_at: target.created_at,
    updated_at: target.updated_at,
    members: entities.map((entity, position) => ({
      id: `member-${position}`,
      position,
      entity,
      added_by_user_id: "controlled-list-user",
      created_at: target.created_at,
    })),
  };
  const policy: CollectionPolicy = {
    id: "controlled-policy",
    policy_version: "workspace-export-v1",
    enabled: true,
    allowed_formats: ["json", "xlsx"],
    allowed_fields: ["position", "id", "entity_type", "name", "description"],
    max_records_per_export: 20,
    attribution: "原始许可 / exact attribution",
    configured_by_user_id: detail.owner_user_id,
    policy_sha256: "a".repeat(64),
    created_at: detail.created_at,
    updated_at: detail.updated_at,
  };
  const history: ComparisonSetVersionRead[] = [
    {
      id: "controlled-history",
      version: 2,
      changed_by_user_id: detail.owner_user_id,
      created_at: detail.updated_at,
      snapshot_json: {
        name: "原始历史标题",
        description: "原始历史说明",
        visibility: "FUTURE_SCOPE",
        member_entity_ids: [],
      },
    },
  ];
  function dossier(id: string): EntityDossier {
    const entity = entities.find((item) => item.id === id);
    if (!entity) throw new Error("Unknown controlled dossier identity");
    return {
      entity,
      as_of: entity.updated_at,
      relationships: [],
      activities: [],
      programs: [],
      clinical_trials: [],
      patents: [],
      deals: [],
      regulatory_events: [],
      news_events: [],
      structures: [],
      target_evidence: [],
      coverage: [{ domain: "programs", total: 1200, returned: 50, status: "truncated", note: "原始覆盖说明" }],
      warnings: [],
    };
  }
  const drugComparison: DrugComparison = {
    as_of: detail.updated_at,
    query_schema_version: "pharma.drug.comparison.v1",
    items: drugs.map((entity) => ({
      entity,
      as_of: entity.updated_at,
      target_names: ["EGFR"],
      indication_names: ["原始适应症"],
      organization_names: ["原始研发机构"],
      program_status_counts: { active: 1200, FUTURE_STATUS: 0 },
      summary: {
        program_count: 1200,
        target_count: 1,
        indication_count: 1,
        organization_count: 1,
        modalities: ["SMALL_MOLECULE", "FUTURE_MODALITY"],
        highest_phase: "phase_2",
        highest_global_phase: "phase_2",
        highest_china_phase: "phase_1",
        latest_status_date: null,
      },
    })),
  };
  return { detail, entities, target, company, drugs, policy, history, dossier, drugComparison };
}
