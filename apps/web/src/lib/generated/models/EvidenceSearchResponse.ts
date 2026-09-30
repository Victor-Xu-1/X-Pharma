/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EvidenceChunk } from './EvidenceChunk';
import type { EvidenceLicenseScope } from './EvidenceLicenseScope';
export type EvidenceSearchResponse = {
  chunks: Array<EvidenceChunk>;
  engine: string;
  license_scopes: Array<EvidenceLicenseScope>;
  query: string;
  warnings?: Array<string>;
};
