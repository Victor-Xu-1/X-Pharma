/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SarActivityRead } from './SarActivityRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_SarActivityRead_ = {
  items: Array<SarActivityRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
