/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SortCriterionRead } from './SortCriterionRead';
import type { TargetEvidenceRead } from './TargetEvidenceRead';
export type AgentPageResult_TargetEvidenceRead_ = {
  items: Array<TargetEvidenceRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
