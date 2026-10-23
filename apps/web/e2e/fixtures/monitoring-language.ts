import type {
  MonitoringAlert,
  MonitoringSnapshot,
  MonitoringTopic,
  SavedSearch,
} from "../../src/lib/contracts/monitoring";

/** Synthetic browser-only records; never publish these as scientific evidence. */
export function monitoringLanguageFixture(): MonitoringSnapshot {
  const saved: SavedSearch = {
    id: "controlled-trial-search",
    owner_user_id: "controlled-monitor-user",
    name: "原始检索名称 / trial watch",
    description: "原始研究范围 <script> — literal fixture, not a real study",
    query_type: "clinical_trial_search",
    query_version: 2,
    visibility: "tenant",
    query_json: {
      q: "原始 EGFR 关键词",
      status: "RECRUITING",
      phase: "PHASE2",
      has_results: false,
      investigational_drug: "原始药物名称",
      linked_drug_modality: ["SMALL_MOLECULE", "FUTURE_MODALITY"],
      disclosed_from: "2026-02-01",
      role_entity_ids: ["opaque-fixture-one", "opaque-fixture-two"],
      sort_by: "enrollment",
      sort_direction: "desc",
    },
    created_at: "2026-10-09T00:00:00Z",
    updated_at: "2026-10-09T00:00:00Z",
  };
  const structure: SavedSearch = {
    ...saved,
    id: "controlled-chemistry-search",
    name: "Controlled structure search",
    query_type: "chemistry_search",
    query_json: { mode: "similarity", query: "CC(=O)Oc1ccccc1C(=O)O", threshold: 0, limit: 20 },
  };
  const topic: MonitoringTopic = {
    id: "controlled-pinned-topic",
    owner_user_id: saved.owner_user_id,
    saved_search_id: saved.id,
    name: "原始固定主题",
    query_version: 1,
    active: true,
    created_at: saved.created_at,
    updated_at: saved.updated_at,
  };
  const alert: MonitoringAlert = {
    id: "controlled-alert",
    topic_id: topic.id,
    topic_name: topic.name,
    entity_id: "550e8400-e29b-41d4-a716-446655440051",
    entity_name: "原始 EGFR 名称",
    event_type: "governance.fact.published",
    title: "Original event title",
    summary: "原始变更摘要 <script> — not a real study",
    payload_json: {},
    occurred_at: saved.updated_at,
    read_at: null,
  };
  return {
    searches: [saved, structure],
    topics: [topic, { ...topic, id: "controlled-paused-topic", name: "Paused fixture", active: false }],
    alerts: [alert],
  };
}
