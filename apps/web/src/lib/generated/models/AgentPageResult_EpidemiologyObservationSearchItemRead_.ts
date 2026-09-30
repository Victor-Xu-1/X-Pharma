/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EpidemiologyObservationSearchItemRead } from './EpidemiologyObservationSearchItemRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type AgentPageResult_EpidemiologyObservationSearchItemRead_ = {
  items: Array<EpidemiologyObservationSearchItemRead>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  sort?: Array<SortCriterionRead>;
};
