/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataQualityCoverageRead } from '../models/DataQualityCoverageRead';
import type { DataQualityIssueActionRequest } from '../models/DataQualityIssueActionRequest';
import type { DataQualityIssueEventRead } from '../models/DataQualityIssueEventRead';
import type { DataQualityIssueRead } from '../models/DataQualityIssueRead';
import type { DataQualityOwnerRead } from '../models/DataQualityOwnerRead';
import type { DataQualitySnapshotRead } from '../models/DataQualitySnapshotRead';
import type { EntityOntologyMappingCreate } from '../models/EntityOntologyMappingCreate';
import type { EntityResolutionCaseRead } from '../models/EntityResolutionCaseRead';
import type { EntityResolutionDecisionRequest } from '../models/EntityResolutionDecisionRequest';
import type { EntityResolutionImpactRead } from '../models/EntityResolutionImpactRead';
import type { EntityType } from '../models/EntityType';
import type { GovernanceFactComparisonRead } from '../models/GovernanceFactComparisonRead';
import type { GovernanceRunPageRead } from '../models/GovernanceRunPageRead';
import type { OntologyTermRead } from '../models/OntologyTermRead';
import type { OntologyTermUpsert } from '../models/OntologyTermUpsert';
import type { ProjectionMaintenanceAccessRead } from '../models/ProjectionMaintenanceAccessRead';
import type { ProjectionMaintenanceJobRead } from '../models/ProjectionMaintenanceJobRead';
import type { ProjectionMaintenanceRequest } from '../models/ProjectionMaintenanceRequest';
import type { PublicationBatchCommitRequest } from '../models/PublicationBatchCommitRequest';
import type { PublicationBatchPreviewRequest } from '../models/PublicationBatchPreviewRequest';
import type { PublicationBatchRead } from '../models/PublicationBatchRead';
import type { ResolutionStatus } from '../models/ResolutionStatus';
import type { ReviewDecision } from '../models/ReviewDecision';
import type { RunState } from '../models/RunState';
import type { StagedFactRead } from '../models/StagedFactRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class GovernanceService {
  /**
   * Create Entity Ontology Mapping
   * @returns any Successful Response
   * @throws ApiError
   */
  public static createEntityOntologyMappingApiV1GovernanceEntitiesEntityIdOntologyMappingsPost({
    entityId,
    requestBody,
  }: {
    entityId: string,
    requestBody: EntityOntologyMappingCreate,
  }): CancelablePromise<Record<string, any>> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/entities/{entity_id}/ontology-mappings',
      path: {
        'entity_id': entityId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Entity Resolution Cases
   * @returns EntityResolutionCaseRead Successful Response
   * @throws ApiError
   */
  public static listEntityResolutionCasesApiV1GovernanceEntityResolutionCasesGet({
    status = 'pending',
    limit = 100,
  }: {
    status?: ResolutionStatus,
    limit?: number,
  }): CancelablePromise<Array<EntityResolutionCaseRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/entity-resolution-cases',
      query: {
        'status': status,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Decide Entity Resolution Case
   * @returns EntityResolutionCaseRead Successful Response
   * @throws ApiError
   */
  public static decideEntityResolutionCaseApiV1GovernanceEntityResolutionCasesCaseIdDecisionPost({
    caseId,
    requestBody,
  }: {
    caseId: string,
    requestBody: EntityResolutionDecisionRequest,
  }): CancelablePromise<EntityResolutionCaseRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/entity-resolution-cases/{case_id}/decision',
      path: {
        'case_id': caseId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Entity Resolution Case Impact
   * @returns EntityResolutionImpactRead Successful Response
   * @throws ApiError
   */
  public static getEntityResolutionCaseImpactApiV1GovernanceEntityResolutionCasesCaseIdImpactGet({
    caseId,
  }: {
    caseId: string,
  }): CancelablePromise<EntityResolutionImpactRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/entity-resolution-cases/{case_id}/impact',
      path: {
        'case_id': caseId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Identifier Namespaces
   * @returns any Successful Response
   * @throws ApiError
   */
  public static listIdentifierNamespacesApiV1GovernanceIdentityNamespacesGet(): CancelablePromise<Array<Record<string, any>>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/identity/namespaces',
    });
  }
  /**
   * List Ontology Terms
   * @returns OntologyTermRead Successful Response
   * @throws ApiError
   */
  public static listOntologyTermsApiV1GovernanceOntologyTermsGet({
    ontologyName,
    entityType,
    limit = 100,
  }: {
    ontologyName?: (string | null),
    entityType?: (EntityType | null),
    limit?: number,
  }): CancelablePromise<Array<OntologyTermRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/ontology/terms',
      query: {
        'ontology_name': ontologyName,
        'entity_type': entityType,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Register Ontology Term
   * @returns OntologyTermRead Successful Response
   * @throws ApiError
   */
  public static registerOntologyTermApiV1GovernanceOntologyTermsPost({
    requestBody,
  }: {
    requestBody: OntologyTermUpsert,
  }): CancelablePromise<OntologyTermRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/ontology/terms',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Projection Maintenance Access
   * @returns ProjectionMaintenanceAccessRead Successful Response
   * @throws ApiError
   */
  public static getProjectionMaintenanceAccessApiV1GovernanceProjectionMaintenanceAccessGet(): CancelablePromise<ProjectionMaintenanceAccessRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/projection-maintenance-access',
    });
  }
  /**
   * List Projection Maintenance Jobs
   * @returns ProjectionMaintenanceJobRead Successful Response
   * @throws ApiError
   */
  public static listProjectionMaintenanceJobsApiV1GovernanceProjectionMaintenanceJobsGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<ProjectionMaintenanceJobRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/projection-maintenance-jobs',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Request Projection Maintenance Job
   * @returns ProjectionMaintenanceJobRead Successful Response
   * @throws ApiError
   */
  public static requestProjectionMaintenanceJobApiV1GovernanceProjectionMaintenanceJobsPost({
    requestBody,
  }: {
    requestBody: ProjectionMaintenanceRequest,
  }): CancelablePromise<ProjectionMaintenanceJobRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/projection-maintenance-jobs',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Projection Maintenance Job
   * @returns ProjectionMaintenanceJobRead Successful Response
   * @throws ApiError
   */
  public static getProjectionMaintenanceJobApiV1GovernanceProjectionMaintenanceJobsJobIdGet({
    jobId,
  }: {
    jobId: string,
  }): CancelablePromise<ProjectionMaintenanceJobRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/projection-maintenance-jobs/{job_id}',
      path: {
        'job_id': jobId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Publication Batches
   * @returns PublicationBatchRead Successful Response
   * @throws ApiError
   */
  public static listPublicationBatchesApiV1GovernancePublicationBatchesGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<PublicationBatchRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/publication-batches',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Preview Publication Batch
   * @returns PublicationBatchRead Successful Response
   * @throws ApiError
   */
  public static previewPublicationBatchApiV1GovernancePublicationBatchesPreviewPost({
    requestBody,
  }: {
    requestBody: PublicationBatchPreviewRequest,
  }): CancelablePromise<PublicationBatchRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/publication-batches/preview',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Publication Batch
   * @returns PublicationBatchRead Successful Response
   * @throws ApiError
   */
  public static getPublicationBatchApiV1GovernancePublicationBatchesBatchIdGet({
    batchId,
  }: {
    batchId: string,
  }): CancelablePromise<PublicationBatchRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/publication-batches/{batch_id}',
      path: {
        'batch_id': batchId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Commit Publication Batch
   * @returns PublicationBatchRead Successful Response
   * @throws ApiError
   */
  public static commitPublicationBatchApiV1GovernancePublicationBatchesBatchIdCommitPost({
    batchId,
    requestBody,
  }: {
    batchId: string,
    requestBody: PublicationBatchCommitRequest,
  }): CancelablePromise<PublicationBatchRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/publication-batches/{batch_id}/commit',
      path: {
        'batch_id': batchId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Data Quality Coverage
   * @returns DataQualityCoverageRead Successful Response
   * @throws ApiError
   */
  public static listDataQualityCoverageApiV1GovernanceQualityCoverageGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<DataQualityCoverageRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/quality/coverage',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Evaluate Data Quality
   * @returns DataQualitySnapshotRead Successful Response
   * @throws ApiError
   */
  public static evaluateDataQualityApiV1GovernanceQualityEvaluationsPost(): CancelablePromise<DataQualitySnapshotRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/quality/evaluations',
    });
  }
  /**
   * List Data Quality Issues
   * @returns DataQualityIssueRead Successful Response
   * @throws ApiError
   */
  public static listDataQualityIssuesApiV1GovernanceQualityIssuesGet({
    status,
    limit = 200,
  }: {
    status?: ('open' | 'acknowledged' | 'ready_to_resolve' | 'resolved' | 'waived' | null),
    limit?: number,
  }): CancelablePromise<Array<DataQualityIssueRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/quality/issues',
      query: {
        'status': status,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Act On Data Quality Issue
   * @returns DataQualityIssueRead Successful Response
   * @throws ApiError
   */
  public static actOnDataQualityIssueApiV1GovernanceQualityIssuesIssueIdActionsPost({
    issueId,
    requestBody,
  }: {
    issueId: string,
    requestBody: DataQualityIssueActionRequest,
  }): CancelablePromise<DataQualityIssueRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/quality/issues/{issue_id}/actions',
      path: {
        'issue_id': issueId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Data Quality Issue Events
   * @returns DataQualityIssueEventRead Successful Response
   * @throws ApiError
   */
  public static listDataQualityIssueEventsApiV1GovernanceQualityIssuesIssueIdEventsGet({
    issueId,
  }: {
    issueId: string,
  }): CancelablePromise<Array<DataQualityIssueEventRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/quality/issues/{issue_id}/events',
      path: {
        'issue_id': issueId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Data Quality Owners
   * @returns DataQualityOwnerRead Successful Response
   * @throws ApiError
   */
  public static listDataQualityOwnersApiV1GovernanceQualityOwnersGet(): CancelablePromise<Array<DataQualityOwnerRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/quality/owners',
    });
  }
  /**
   * List Data Quality Snapshots
   * @returns DataQualitySnapshotRead Successful Response
   * @throws ApiError
   */
  public static listDataQualitySnapshotsApiV1GovernanceQualitySnapshotsGet({
    limit = 30,
  }: {
    limit?: number,
  }): CancelablePromise<Array<DataQualitySnapshotRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/quality/snapshots',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Review Queue
   * @returns StagedFactRead Successful Response
   * @throws ApiError
   */
  public static listReviewQueueApiV1GovernanceReviewQueueGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<StagedFactRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/review-queue',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Governance Runs
   * @returns GovernanceRunPageRead Successful Response
   * @throws ApiError
   */
  public static listGovernanceRunsApiV1GovernanceRunsGet({
    status,
    limit = 50,
    offset,
  }: {
    status?: (RunState | null),
    limit?: number,
    offset?: number,
  }): CancelablePromise<GovernanceRunPageRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/runs',
      query: {
        'status': status,
        'limit': limit,
        'offset': offset,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Staged Fact Comparison
   * @returns GovernanceFactComparisonRead Successful Response
   * @throws ApiError
   */
  public static getStagedFactComparisonApiV1GovernanceStagedFactsStagedFactIdComparisonGet({
    stagedFactId,
  }: {
    stagedFactId: string,
  }): CancelablePromise<GovernanceFactComparisonRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/governance/staged-facts/{staged_fact_id}/comparison',
      path: {
        'staged_fact_id': stagedFactId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Decide Staged Fact
   * @returns StagedFactRead Successful Response
   * @throws ApiError
   */
  public static decideStagedFactApiV1GovernanceStagedFactsStagedFactIdDecisionPost({
    stagedFactId,
    requestBody,
  }: {
    stagedFactId: string,
    requestBody: ReviewDecision,
  }): CancelablePromise<StagedFactRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/governance/staged-facts/{staged_fact_id}/decision',
      path: {
        'staged_fact_id': stagedFactId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
