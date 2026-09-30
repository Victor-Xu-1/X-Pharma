/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BioactivityRead } from './BioactivityRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_BioactivityRead_ = {
  items: Array<BioactivityRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
