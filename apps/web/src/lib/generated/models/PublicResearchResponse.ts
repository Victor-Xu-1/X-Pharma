/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { PublicResearchSourceResult } from './PublicResearchSourceResult';
export type PublicResearchResponse = {
  observed_at: string;
  persisted?: boolean;
  query: string;
  results: Array<PublicResearchSourceResult>;
};
