/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { NewsEventSearchItemRead } from './NewsEventSearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_NewsEventSearchItemRead_ = {
  items: Array<NewsEventSearchItemRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
