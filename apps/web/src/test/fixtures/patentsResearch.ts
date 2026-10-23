import type { PatentFamilySearchResult } from "../../lib/generated";

/** Synthetic test records only, never ingested or presented as actual patent coverage. */
export const patentResult = {
  items: [
    {
      id: "patent-1",
      entity_id: "550e8400-e29b-41d4-a716-446655440001",
      family_identifier: "INPADOC-123456",
      title: "EGFR kinase inhibitors for treating NSCLC",
      priority_date: "2021-02-03",
      applicants: ["Victor Therapeutics"],
      inventors: ["Wei Chen", "Lin Zhang"],
      publications: [{ publication_number: "WO2022123456A1" }],
      legal_status: "ACTIVE",
      legal_status_at: "2026-06-01T00:00:00Z",
      legal_events: [
        {
          event_type: "grant",
          status: "ACTIVE",
          occurred_at: "2026-06-01T00:00:00Z",
          jurisdiction: "WO",
          publication_number: "WO2022123456A1",
        },
      ],
      independent_claims: [
        {
          claim_number: "1",
          claim_type: "composition" as const,
          summary: "Composition covering an EGFR kinase inhibitor.",
        },
      ],
      expiration_date: "2042-02-03",
      linked_entity_ids: ["550e8400-e29b-41d4-a716-446655440002"],
      source_document_id: null,
      linked_entities: [{ id: "550e8400-e29b-41d4-a716-446655440002", name: "EGFR", entity_type: "target" as const }],
    },
  ],
  total: 101,
  limit: 100,
  offset: 0,
  query_schema_version: "pharma.patent.search.v2",
  applied_filters: [],
  sort_by: "priority_date" as const,
  sort_direction: "desc" as const,
  facets: {
    applicant: { "Victor Therapeutics": 101 },
    legal_status: { ACTIVE: 101 },
  },
  landscape: {
    total_families: 101,
    legal_status: [{ key: "ACTIVE", label: "ACTIVE", count: 101, share: 1 }],
    top_applicants: [{ key: "Victor Therapeutics", label: "Victor Therapeutics", count: 101, share: 1 }],
    priority_year: [{ key: "2024", label: "2024", count: 101, share: 1 }],
  },
  as_of: "2026-07-22T10:00:00Z",
  warnings: ["结果受当前数据授权、法律状态时效和治理状态限制。"],
} satisfies PatentFamilySearchResult;
