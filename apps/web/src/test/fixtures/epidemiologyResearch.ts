/** Original synthetic UI fixture; not real epidemiology evidence or ingestion input. */
import type { EpidemiologyFilters } from "../../lib/contracts/epidemiology";

export const emptyFilters: EpidemiologyFilters = {
  query: "",
  diseaseEntityId: "",
  measure: "",
  geography: "",
  unit: "",
  patientPopulationId: "",
  populationScope: "",
  ageGroup: "",
  sex: "",
  periodStartFrom: "",
  periodEndTo: "",
  displayMode: "list" as const,
  analysisView: "chart" as const,
  sortBy: "period_end" as const,
  sortDirection: "desc" as const,
};

export const observation = {
  id: "observation-1",
  observation_identifier: "WHO-NSCLC-CN-2025",
  disease_entity_id: "550e8400-e29b-41d4-a716-446655440001",
  patient_population_id: "550e8400-e29b-41d4-a716-446655440003",
  measure: "prevalence",
  value: 158000,
  lower_bound: 150000,
  upper_bound: 166000,
  unit: "patients",
  geography: "China",
  population_scope: "adults",
  age_group: "18+",
  sex: "all",
  period_start: "2025-01-01T00:00:00Z",
  period_end: "2025-12-31T00:00:00Z",
  sample_size: 12500,
  methodology: "Registry-calibrated prevalence model",
  publisher_entity_id: "550e8400-e29b-41d4-a716-446655440002",
  source_document_id: "source-1",
  disease_entity: {
    id: "550e8400-e29b-41d4-a716-446655440001",
    name: "EGFR-positive NSCLC",
    entity_type: "disease" as const,
  },
  publisher_entity: {
    id: "550e8400-e29b-41d4-a716-446655440002",
    name: "WHO",
    entity_type: "organization" as const,
  },
  patient_population: {
    id: "550e8400-e29b-41d4-a716-446655440003",
    population_key: "egfr-positive-nsclc-cn",
    name: "中国 EGFR 阳性 NSCLC 患者",
    description: "标准化生物标志物患者人群",
    attributes: { biomarker: "EGFR-positive" },
    disease_entities: [
      {
        id: "550e8400-e29b-41d4-a716-446655440001",
        name: "EGFR-positive NSCLC",
        entity_type: "disease" as const,
      },
    ],
    target_entities: [
      {
        id: "550e8400-e29b-41d4-a716-446655440004",
        name: "EGFR",
        entity_type: "target" as const,
      },
    ],
  },
};

export const searchResult = {
  items: [observation],
  total: 101,
  limit: 100,
  offset: 0,
  facets: {
    measure: { prevalence: 101 },
    geography: { China: 101 },
    unit: { patients: 101 },
    population_scope: { adults: 101 },
    age_group: { "18+": 101 },
    sex: { all: 101 },
    disease: { "EGFR-positive NSCLC": 101 },
    publisher: { WHO: 101 },
  },
  patient_populations: [{ id: "550e8400-e29b-41d4-a716-446655440003", name: "中国 EGFR 阳性 NSCLC 患者", count: 101 }],
  landscape: {
    total_observations: 1,
    measure: [{ key: "prevalence", label: "prevalence", count: 1, share: 1 }],
    geography: [{ key: "China", label: "China", count: 1, share: 1 }],
    population_scope: [{ key: "adults", label: "adults", count: 1, share: 1 }],
  },
  as_of: "2026-07-22T10:00:00Z",
  query_schema_version: "pharma.epidemiology.search.v3",
  sort_by: "period_end" as const,
  sort_direction: "desc" as const,
  applied_filters: [
    { field: "q", operator: "contains" as const, value: "NSCLC" },
    { field: "geography", operator: "eq" as const, value: "China" },
  ],
  warnings: ["未观察到估计不代表患者不存在。"],
};
