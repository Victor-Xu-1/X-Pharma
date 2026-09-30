/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { ChemistrySearchRead } from '../models/ChemistrySearchRead';
import type { ChemistrySearchRequest } from '../models/ChemistrySearchRequest';
import type { CompoundStructureRead } from '../models/CompoundStructureRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class StructuresService {
  /**
   * Search Chemistry
   * @returns ChemistrySearchRead Successful Response
   * @throws ApiError
   */
  public static searchChemistryApiV1ChemistrySearchPost({
    requestBody,
  }: {
    requestBody: ChemistrySearchRequest,
  }): CancelablePromise<ChemistrySearchRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/chemistry/search',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Search Structures
   * @returns CompoundStructureRead Successful Response
   * @throws ApiError
   */
  public static searchStructuresApiV1StructuresGet({
    entityId,
    inchiKey,
    limit = 50,
  }: {
    entityId?: (string | null),
    inchiKey?: (string | null),
    limit?: number,
  }): CancelablePromise<Array<CompoundStructureRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/structures',
      query: {
        'entity_id': entityId,
        'inchi_key': inchiKey,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
