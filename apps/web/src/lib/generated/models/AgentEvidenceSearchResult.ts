/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EvidenceChunk } from './EvidenceChunk';
import type { EvidenceLicenseScope } from './EvidenceLicenseScope';
export type AgentEvidenceSearchResult = {
  chunks: Array<EvidenceChunk>;
  engine: string;
  license_scopes: Array<EvidenceLicenseScope>;
  limit: number;
  next_cursor: (string | null);
  page_depth: number;
  query: string;
  warnings?: Array<string>;
};
