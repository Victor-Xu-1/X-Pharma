/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Routing rule retained for the public ChEMBL connector.
 *
 * ChEMBL sources were registered before PubMed and ClinicalTrials.gov routing
 * rules became a tagged union. Keep the persisted target identifier explicit so
 * existing sources remain readable and new registrations use the same contract.
 */
export type ChemblDataSourceRoutingRule = {
  max_records?: number;
  page_size?: number;
  sync_mode?: 'snapshot' | 'continuous';
  target_chembl_id: string;
};
