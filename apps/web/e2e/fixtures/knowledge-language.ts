import type {
  KnowledgeCoverage,
  KnowledgeDetail,
  KnowledgeSearchResult,
  KnowledgeVersion,
  KnowledgeVersionDiff,
} from "../../src/lib/contracts/knowledge";

/** Synthetic immutable read responses, never published as scientific evidence. */
export function knowledgeLanguageFixture() {
  const value = {
    fact_kind: "trial",
    registry_id: "NCT-FIXTURE-ONLY",
    overall_status: "COMPLETED",
    phases: ["PHASE2", "FUTURE_PHASE"],
    enrollment: 0,
    completion_date: "2028-02-01T00:00:00Z",
    completion_date_precision: "month",
    result_evaluation: false,
  };
  const detail: KnowledgeDetail = {
    id: "550e8400-e29b-41d4-a716-446655440031",
    title:
      "Controlled topic / 原始标题 — a deliberately long immutable research topic name for directory readability, not a real study",
    page_type: "target",
    version_number: 2,
    updated_at: "2026-10-09T00:00:00Z",
    source_snapshot_at: "2026-10-08T00:00:00Z",
    rendered_markdown: `## Evidence\n\n- **has_trial**: \`${JSON.stringify(value)}\` [^1]\n\n[^1]: 原始引用 / Exact source [public source](https://example.test/source)`,
  };
  const search: KnowledgeSearchResult = {
    items: [detail],
    limit: 50,
    offset: 0,
    total: 1,
    facets: { page_type: { target: 1 } },
    as_of: detail.updated_at,
    sort_by: "title",
    sort_direction: "asc",
  };
  const coverage: KnowledgeCoverage = {
    fact_count: 1,
    cited_fact_count: 1,
    linked_entity_count: 0,
    source_count: 1,
    uncited_fact_count: 0,
    version_number: 2,
    source_snapshot_at: detail.source_snapshot_at,
    predicates: [{ predicate: "has_trial", fact_count: 1, cited_fact_count: 1 }],
  };
  const versions: KnowledgeVersion[] = [2, 1].map((version) => ({
    version_number: version,
    previous_version_number: version === 2 ? 1 : null,
    source_snapshot_at: detail.source_snapshot_at,
    is_current: version === 2,
    added_fact_count: 1,
    removed_fact_count: 0,
    added_source_count: 1,
    removed_source_count: 0,
  }));
  const diff: KnowledgeVersionDiff = {
    from_version_number: 1,
    to_version_number: 2,
    added_fact_count: 1,
    removed_fact_count: 0,
    added_source_count: 1,
    removed_source_count: 0,
    added_facts: [
      {
        change_key: "controlled-change",
        predicate: "has_trial",
        object_entity_name: null,
        source_title: "原始引用 / Exact source",
        source_locator: "page=4;paragraph=2",
        value,
      },
    ],
    removed_facts: [],
    added_sources: [{ title: "原始引用 / Exact source", locator: "page=4;paragraph=2" }],
    removed_sources: [],
    truncated: false,
  };
  return { detail, search, coverage, versions, diff };
}
