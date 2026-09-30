/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type ChemistrySearchRequest = {
  limit?: number;
  mode: 'exact' | 'substructure' | 'similarity';
  query: string;
  threshold?: number;
};
