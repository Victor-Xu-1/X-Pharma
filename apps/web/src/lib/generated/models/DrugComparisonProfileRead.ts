/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DrugDossierSummaryRead } from './DrugDossierSummaryRead';
import type { EntityRead } from './EntityRead';
/**
 * Complete, server-computed development profile for one compared drug.
 */
export type DrugComparisonProfileRead = {
  as_of: string;
  entity: EntityRead;
  indication_names: Array<string>;
  organization_names: Array<string>;
  program_status_counts: Record<string, number>;
  summary: DrugDossierSummaryRead;
  target_names: Array<string>;
};
