/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompoundStructureRead } from './CompoundStructureRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_CompoundStructureRead_ = {
  items: Array<CompoundStructureRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
