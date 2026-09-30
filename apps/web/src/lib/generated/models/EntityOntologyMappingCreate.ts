/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type EntityOntologyMappingCreate = {
  confidence: number;
  evidence?: Record<string, any>;
  mapping_type: 'exact' | 'broad' | 'narrow' | 'related';
  ontology_term_id: string;
  source_document_id?: (string | null);
};
