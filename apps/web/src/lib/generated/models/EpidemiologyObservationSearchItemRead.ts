/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EpidemiologyLinkedEntityRead } from './EpidemiologyLinkedEntityRead';
import type { PatientPopulationRead } from './PatientPopulationRead';
export type EpidemiologyObservationSearchItemRead = {
  age_group: (string | null);
  disease_entity: EpidemiologyLinkedEntityRead;
  disease_entity_id: string;
  geography: string;
  id: string;
  lower_bound: (number | null);
  measure: string;
  methodology: (string | null);
  observation_identifier: string;
  patient_population: (PatientPopulationRead | null);
  patient_population_id: (string | null);
  period_end: (string | null);
  period_start: (string | null);
  population_scope: string;
  publisher_entity: (EpidemiologyLinkedEntityRead | null);
  publisher_entity_id: (string | null);
  sample_size: (number | null);
  sex: (string | null);
  source_document_id: (string | null);
  unit: string;
  upper_bound: (number | null);
  value: number;
};
