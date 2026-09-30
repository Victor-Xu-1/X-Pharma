/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EpidemiologyObservationSearchResult } from '../models/EpidemiologyObservationSearchResult';
import type { EpidemiologyTrendResult } from '../models/EpidemiologyTrendResult';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class EpidemiologyService {
  /**
   * Search Epidemiology Observations
   * @returns EpidemiologyObservationSearchResult Successful Response
   * @throws ApiError
   */
  public static searchEpidemiologyObservationsApiV1EpidemiologyObservationsGet({
    q,
    diseaseEntityId,
    measure,
    geography,
    unit,
    populationScope,
    patientPopulationId,
    ageGroup,
    sex,
    periodStartFrom,
    periodEndTo,
    limit = 100,
    offset,
    sortBy,
    sortDirection,
    sort,
  }: {
    q?: (string | null),
    diseaseEntityId?: (string | null),
    measure?: (string | null),
    geography?: (string | null),
    unit?: (string | null),
    populationScope?: (string | null),
    patientPopulationId?: (string | null),
    ageGroup?: (string | null),
    sex?: (string | null),
    periodStartFrom?: (string | null),
    periodEndTo?: (string | null),
    limit?: number,
    offset?: number,
    sortBy?: ('period_end' | 'period_start' | 'disease' | 'measure' | 'value' | 'geography' | 'unit' | 'publisher' | 'sample_size' | null),
    sortDirection?: ('asc' | 'desc' | null),
    sort?: (Array<string> | null),
  }): CancelablePromise<EpidemiologyObservationSearchResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/epidemiology-observations',
      query: {
        'q': q,
        'disease_entity_id': diseaseEntityId,
        'measure': measure,
        'geography': geography,
        'unit': unit,
        'population_scope': populationScope,
        'patient_population_id': patientPopulationId,
        'age_group': ageGroup,
        'sex': sex,
        'period_start_from': periodStartFrom,
        'period_end_to': periodEndTo,
        'limit': limit,
        'offset': offset,
        'sort_by': sortBy,
        'sort_direction': sortDirection,
        'sort': sort,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Epidemiology Trend
   * @returns EpidemiologyTrendResult Successful Response
   * @throws ApiError
   */
  public static getEpidemiologyTrendApiV1EpidemiologyTrendsDiseaseEntityIdGet({
    diseaseEntityId,
    measure,
    geography,
    unit,
    populationScope,
    patientPopulationId,
    ageGroup,
    sex,
    anchorObservationId,
    limit = 200,
  }: {
    diseaseEntityId: string,
    measure?: (string | null),
    geography?: (string | null),
    unit?: (string | null),
    populationScope?: (string | null),
    patientPopulationId?: (string | null),
    ageGroup?: (string | null),
    sex?: (string | null),
    anchorObservationId?: (string | null),
    limit?: number,
  }): CancelablePromise<EpidemiologyTrendResult> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/epidemiology-trends/{disease_entity_id}',
      path: {
        'disease_entity_id': diseaseEntityId,
      },
      query: {
        'measure': measure,
        'geography': geography,
        'unit': unit,
        'population_scope': populationScope,
        'patient_population_id': patientPopulationId,
        'age_group': ageGroup,
        'sex': sex,
        'anchor_observation_id': anchorObservationId,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
