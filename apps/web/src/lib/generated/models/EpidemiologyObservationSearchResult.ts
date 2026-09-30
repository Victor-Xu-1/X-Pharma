/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { AppliedFilterRead } from './AppliedFilterRead';
import type { EpidemiologyLandscapeRead } from './EpidemiologyLandscapeRead';
import type { EpidemiologyObservationSearchItemRead } from './EpidemiologyObservationSearchItemRead';
import type { PatientPopulationOptionRead } from './PatientPopulationOptionRead';
import type { SortCriterionRead } from './SortCriterionRead';
export type EpidemiologyObservationSearchResult = {
  applied_filters?: Array<AppliedFilterRead>;
  as_of: string;
  facets: Record<string, Record<string, number>>;
  items: Array<EpidemiologyObservationSearchItemRead>;
  landscape: EpidemiologyLandscapeRead;
  limit: number;
  offset: number;
  patient_populations: Array<PatientPopulationOptionRead>;
  query_schema_version: string;
  sort?: Array<SortCriterionRead>;
  sort_by: 'period_end' | 'period_start' | 'disease' | 'measure' | 'value' | 'geography' | 'unit' | 'publisher' | 'sample_size';
  sort_direction: 'asc' | 'desc';
  total: number;
  warnings: Array<string>;
};
