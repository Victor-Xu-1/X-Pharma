/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { EvidenceDatasetRead } from '../models/EvidenceDatasetRead';
import type { EvidenceSearchRequest } from '../models/EvidenceSearchRequest';
import type { EvidenceSearchResponse } from '../models/EvidenceSearchResponse';
import type { RecordProvenanceResponse } from '../models/RecordProvenanceResponse';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class EvidenceService {
  /**
   * List Evidence Datasets
   * @returns EvidenceDatasetRead Successful Response
   * @throws ApiError
   */
  public static listEvidenceDatasetsApiV1EvidenceDatasetsGet(): CancelablePromise<Array<EvidenceDatasetRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/evidence/datasets',
    });
  }
  /**
   * Search Evidence
   * @returns EvidenceSearchResponse Successful Response
   * @throws ApiError
   */
  public static searchEvidenceApiV1EvidenceSearchPost({
    requestBody,
  }: {
    requestBody: EvidenceSearchRequest,
  }): CancelablePromise<EvidenceSearchResponse> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/evidence/search',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Record Provenance
   * @returns RecordProvenanceResponse Successful Response
   * @throws ApiError
   */
  public static getRecordProvenanceApiV1ProvenanceResourceTypeResourceIdGet({
    resourceType,
    resourceId,
    limit = 20,
  }: {
    resourceType: 'activity_measurement' | 'assay' | 'clinical_trial' | 'compound_structure' | 'deal' | 'development_program' | 'epidemiology_observation' | 'evidence_claim' | 'news_event' | 'patient_population' | 'patent_family' | 'regulatory_event' | 'target_profile' | 'target_evidence',
    resourceId: string,
    limit?: number,
  }): CancelablePromise<RecordProvenanceResponse> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/provenance/{resource_type}/{resource_id}',
      path: {
        'resource_type': resourceType,
        'resource_id': resourceId,
      },
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
