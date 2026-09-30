/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DrugComparisonProfileRead } from './DrugComparisonProfileRead';
/**
 * Bounded batch response used by the human drug comparison workspace.
 */
export type DrugComparisonResult = {
  as_of: string;
  items: Array<DrugComparisonProfileRead>;
  query_schema_version?: string;
};
