/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { CompetitiveProgramRead } from './CompetitiveProgramRead';
/**
 * A paged, human-readable view of one drug's complete development set.
 */
export type DrugProgramSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  items: Array<CompetitiveProgramRead>;
  limit: number;
  offset: number;
  query_schema_version: string;
  total: number;
  warnings?: Array<string>;
};
