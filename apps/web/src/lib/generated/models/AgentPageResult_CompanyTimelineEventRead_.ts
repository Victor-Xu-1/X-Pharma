/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompanyTimelineEventRead } from './CompanyTimelineEventRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_CompanyTimelineEventRead_ = {
  items: Array<CompanyTimelineEventRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
