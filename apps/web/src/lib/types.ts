import type {
  DataSourceDatasetRead,
  DataSourceRead,
  DataSourceReadinessRead,
  IngestionFindingRead,
  IngestionRunRead,
  MonitoringAlertRead,
  MonitoringTopicRead,
  SavedSearchRead,
  UserRead,
} from "./generated";

export type UserRole = UserRead["role"];
export type EntityType =
  | "target"
  | "drug"
  | "organization"
  | "disease"
  | "clinical_trial"
  | "patent"
  | "transaction"
  | "product"
  | "technology"
  | "person";

export type User = Pick<UserRead, "id" | "tenant_id" | "email" | "display_name" | "role"> &
  Partial<Pick<UserRead, "phone" | "avatar_url" | "organization_name">>;

export interface Entity {
  id: string;
  entity_type: EntityType;
  name: string;
  description: string | null;
  external_ids: Record<string, string>;
  attributes: Record<string, unknown>;
  review_status: string;
  canonical_entity_id?: string;
  identity_identifiers?: Array<{
    namespace: string;
    value: string;
    normalized_value: string;
    trusted_namespace: boolean;
    review_status: string;
    source_document_id: string | null;
  }>;
  created_at: string;
  updated_at: string;
}

export interface SearchResult {
  items: Entity[];
  total: number;
  limit: number;
  offset: number;
  facets: Record<string, Record<string, number>>;
  suggestions: string[];
  engine: string;
  took_ms: number | null;
}

export type SavedSearch = SavedSearchRead;
export type MonitoringTopic = MonitoringTopicRead;
export type MonitoringAlert = MonitoringAlertRead;

export interface ComparisonSetSummary {
  id: string;
  owner_user_id: string;
  name: string;
  description: string;
  visibility: "private" | "tenant";
  version: number;
  member_count: number;
  editable: boolean;
  created_at: string;
  updated_at: string;
}

export interface ComparisonSetMember {
  id: string;
  position: number;
  added_by_user_id: string;
  created_at: string;
  entity: Entity;
}

export interface ComparisonSetDetail extends ComparisonSetSummary {
  members: ComparisonSetMember[];
}

export interface WorkspaceExportPolicy {
  id: string;
  policy_version: string;
  enabled: boolean;
  allowed_formats: Array<"csv" | "json" | "xlsx">;
  allowed_fields: string[];
  max_records_per_export: number;
  attribution: string;
  configured_by_user_id: string;
  policy_sha256: string;
  created_at: string;
  updated_at: string;
}

export type DataSource = DataSourceRead;
export type DataSourceDataset = DataSourceDatasetRead;
export type DataSourceReadiness = DataSourceReadinessRead;
export type IngestionRun = IngestionRunRead;
export type IngestionFinding = IngestionFindingRead;
