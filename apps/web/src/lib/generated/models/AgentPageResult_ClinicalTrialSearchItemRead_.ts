/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ClinicalTrialSearchItemRead } from './ClinicalTrialSearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_ClinicalTrialSearchItemRead_ = {
  items: Array<ClinicalTrialSearchItemRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
