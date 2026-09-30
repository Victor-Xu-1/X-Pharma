/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
/**
 * Versioned saved-search payload; the structure stays server-side, not in a URL.
 */
export type ChemistrySavedSearchQuery = {
  limit?: number;
  mode: 'exact' | 'substructure' | 'similarity';
  query: string;
  threshold?: number;
};
