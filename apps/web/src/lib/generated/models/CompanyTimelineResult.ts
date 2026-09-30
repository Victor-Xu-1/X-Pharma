/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { CompanyTimelineEventRead } from './CompanyTimelineEventRead';
import type { EntityRead } from './EntityRead';
export type CompanyTimelineResult = {
  as_of: string;
  company: EntityRead;
  facets?: Record<string, Record<string, number>>;
  items: Array<CompanyTimelineEventRead>;
  limit: number;
  offset: number;
  total: number;
  warnings?: Array<string>;
};
