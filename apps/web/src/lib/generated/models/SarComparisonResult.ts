/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { SarActivityRead } from './SarActivityRead';
export type SarComparisonResult = {
  as_of?: (string | null);
  facets?: Record<string, Record<string, number>>;
  items: Array<SarActivityRead>;
  limit: number;
  offset: number;
  total: number;
  warnings?: Array<string>;
};
