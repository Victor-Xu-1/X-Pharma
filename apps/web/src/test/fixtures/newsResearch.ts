/** Synthetic isolated research fixtures; not real source records or an ingestion input. */
import type { NewsSearchFilters } from "../../lib/contracts/news";
export const initialFilters: NewsSearchFilters = {
  query: "Compound A",
  entityId: "",
  eventType: "",
  publisher: "",
  language: "",
  venue: "",
  publishedFrom: "",
  publishedTo: "",
  contentScope: "",
  displayMode: "list",
  analysisView: "chart",
  sortBy: "published_at",
  sortDirection: "desc",
};
export const newsResult = {
  items: [
    {
      id: "news-1",
      event_identifier: "ACME-ASCO-2026",
      event_type: "corporate_announcement",
      title: "Acme reports positive Phase 2 data for Compound A",
      summary: "The study met its primary endpoint.",
      published_at: "2026-06-05T08:00:00Z",
      language: "en",
      publisher_entity_id: "550e8400-e29b-41d4-a716-446655440001",
      related_entity_ids: ["550e8400-e29b-41d4-a716-446655440002"],
      canonical_url: "https://example.test/acme/compound-a",
      venue: "ASCO 2026",
      details: { data_type: "clinical_update" },
      source_document_id: "document-1",
      publisher_entity: {
        id: "550e8400-e29b-41d4-a716-446655440001",
        name: "Acme Pharma",
        entity_type: "organization" as const,
      },
      related_entities: [
        {
          id: "550e8400-e29b-41d4-a716-446655440002",
          name: "Compound A",
          entity_type: "drug" as const,
        },
      ],
    },
  ],
  total: 101,
  limit: 100,
  offset: 0,
  query_schema_version: "pharma.news.search.v2",
  applied_filters: [],
  sort_by: "published_at" as const,
  sort_direction: "desc" as const,
  facets: {
    event_type: { corporate_announcement: 101 },
    publisher: { "Acme Pharma": 101 },
    language: { en: 101 },
    venue: { "ASCO 2026": 101 },
  },
  landscape: {
    total_events: 1,
    event_type: [{ key: "publication", label: "publication", count: 1, share: 1 }],
    venue: [{ key: "ASCO", label: "ASCO", count: 1, share: 1 }],
    published_year: [{ key: "2026", label: "2026", count: 1, share: 1 }],
  },
  as_of: "2026-07-22T10:00:00Z",
  warnings: ["未观察到动态不代表不存在；结果受数据授权、发布时效和治理状态限制。"],
};
