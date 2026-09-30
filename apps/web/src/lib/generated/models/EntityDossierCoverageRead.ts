/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EntityDossierCoverageRead = {
  domain: 'relationships' | 'evidence' | 'activities' | 'programs' | 'clinical_trials' | 'patents' | 'deals' | 'regulatory_events' | 'news_events' | 'structures' | 'target_evidence';
  note: string;
  returned: number;
  status: 'available' | 'not_observed' | 'truncated';
  total: number;
};
