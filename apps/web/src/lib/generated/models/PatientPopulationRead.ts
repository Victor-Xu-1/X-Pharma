/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EpidemiologyLinkedEntityRead } from './EpidemiologyLinkedEntityRead';
export type PatientPopulationRead = {
  attributes: Record<string, any>;
  description: (string | null);
  disease_entities: Array<EpidemiologyLinkedEntityRead>;
  id: string;
  name: string;
  population_key: string;
  target_entities: Array<EpidemiologyLinkedEntityRead>;
};
