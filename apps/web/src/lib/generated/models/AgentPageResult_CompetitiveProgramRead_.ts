/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompetitiveProgramRead } from './CompetitiveProgramRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_CompetitiveProgramRead_ = {
  items: Array<CompetitiveProgramRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
