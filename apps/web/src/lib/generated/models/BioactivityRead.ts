/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type BioactivityRead = {
  assay_id: string;
  compound_entity_id: string;
  id: string;
  pchembl_value: (number | null);
  reported_relation: string;
  reported_type: string;
  reported_units: (string | null);
  reported_value: string;
  source_activity_id: string;
  source_document_id?: (string | null);
  source_system: string;
  standard_relation: (string | null);
  standard_type: (string | null);
  standard_units: (string | null);
  standard_value: (number | null);
  target_entity_id: (string | null);
};
