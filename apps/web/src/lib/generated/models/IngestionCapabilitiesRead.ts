/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type IngestionCapabilitiesRead = {
  ai_auto_publish_threshold: number;
  ai_governance_enabled: boolean;
  ai_model: (string | null);
  ai_model_configured: boolean;
  allowed_folder_roots: Array<string>;
  asset_only_extensions: Array<string>;
  automatic_scheduling_enabled: boolean;
  deterministic_governance_enabled: boolean;
  durable_workflows_enabled: boolean;
  isolated_parser_enabled: boolean;
  malware_scanning_enabled: boolean;
  parseable_extensions: Array<string>;
};
