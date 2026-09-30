/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { KnowledgePageSummary } from './KnowledgePageSummary';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_KnowledgePageSummary_ = {
  items: Array<KnowledgePageSummary>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
