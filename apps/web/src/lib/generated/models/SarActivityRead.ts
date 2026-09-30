/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type SarActivityRead = {
  assay_format: (string | null);
  assay_id: string;
  assay_type: (string | null);
  canonical_smiles?: (string | null);
  cell_line: (string | null);
  comparability_reasons?: Array<string>;
  comparable: boolean;
  comparison_group: string;
  compound_entity_id: string;
  compound_name: string;
  delta_pchembl?: (number | null);
  id: string;
  organism: (string | null);
  pchembl_value: (number | null);
  potency_rank?: (number | null);
  source_activity_id: string;
  source_document_id?: (string | null);
  source_system: string;
  standard_inchi_key?: (string | null);
  standard_relation: (string | null);
  standard_type: (string | null);
  standard_units: (string | null);
  standard_value: (number | null);
  target_entity_id: string;
  validity_comment?: (string | null);
};
