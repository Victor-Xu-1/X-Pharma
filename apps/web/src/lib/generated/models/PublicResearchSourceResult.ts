/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicResearchRecord } from './PublicResearchRecord';
export type PublicResearchSourceResult = {
  error_code?: ('upstream_unavailable' | 'invalid_response' | null);
  license_notice: string;
  provider: string;
  records?: Array<PublicResearchRecord>;
  scope_note: string;
  source_query_url: string;
  status: 'available' | 'empty' | 'unavailable';
  topic: 'overview' | 'drugs' | 'targets' | 'trials' | 'organizations' | 'conditions' | 'patents' | 'compound_patents' | 'literature' | 'disclosures';
  total?: (number | null);
  warnings?: Array<string>;
};
