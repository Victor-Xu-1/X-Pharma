/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegulatoryEventSearchItemRead } from './RegulatoryEventSearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_RegulatoryEventSearchItemRead_ = {
  items: Array<RegulatoryEventSearchItemRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
