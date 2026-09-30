/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EpidemiologyLinkedEntityRead } from './EpidemiologyLinkedEntityRead';
import type { EpidemiologyObservationSearchItemRead } from './EpidemiologyObservationSearchItemRead';
export type EpidemiologyTrendResult = {
  anchor_observation_id?: (string | null);
  as_of: string;
  disease: EpidemiologyLinkedEntityRead;
  items: Array<EpidemiologyObservationSearchItemRead>;
  total: number;
  truncated: boolean;
  warnings: Array<string>;
};
