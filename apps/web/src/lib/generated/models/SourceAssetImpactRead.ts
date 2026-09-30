/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SourceAssetImpactRead = {
  blockers: Array<string>;
  data_source_id: string;
  evidence_claim_count: number;
  extracted_object_count: number;
  extraction_run_count: number;
  file_name: string;
  id: string;
  knowledge_citation_count: number;
  logical_path: string;
  missing_since: (string | null);
  other_document_reference_count: number;
  published_fact_count: number;
  raw_object_count: number;
  retention_eligible: boolean;
  retrieval_projection_count: number;
  shared_document_count: number;
  staged_fact_count: number;
  state: string;
  version_count: number;
};
