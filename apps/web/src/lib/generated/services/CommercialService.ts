/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { BillingAccountRead } from '../models/BillingAccountRead';
import type { BillingCustomerMappingUpdate } from '../models/BillingCustomerMappingUpdate';
import type { BillingDeliveryRead } from '../models/BillingDeliveryRead';
import type { BillingDeliveryReplayRequest } from '../models/BillingDeliveryReplayRequest';
import type { BillingDisputeCreate } from '../models/BillingDisputeCreate';
import type { BillingDisputeRead } from '../models/BillingDisputeRead';
import type { BillingDisputeTransition } from '../models/BillingDisputeTransition';
import type { BillingStatementCreate } from '../models/BillingStatementCreate';
import type { BillingStatementRead } from '../models/BillingStatementRead';
import type { CommercialAdjustmentRead } from '../models/CommercialAdjustmentRead';
import type { CommercialClientRead } from '../models/CommercialClientRead';
import type { CommercialClientStatusUpdate } from '../models/CommercialClientStatusUpdate';
import type { CommercialExpirationRead } from '../models/CommercialExpirationRead';
import type { CommercialExpirationRequest } from '../models/CommercialExpirationRequest';
import type { CommercialOverviewRead } from '../models/CommercialOverviewRead';
import type { CommercialReconciliationCreate } from '../models/CommercialReconciliationCreate';
import type { CommercialReconciliationRead } from '../models/CommercialReconciliationRead';
import type { CommercialReversalCreate } from '../models/CommercialReversalCreate';
import type { CommercialRiskEventPageRead } from '../models/CommercialRiskEventPageRead';
import type { CommercialRiskEventRead } from '../models/CommercialRiskEventRead';
import type { CommercialRiskReview } from '../models/CommercialRiskReview';
import type { CommercialUsageAdjustmentCreate } from '../models/CommercialUsageAdjustmentCreate';
import type { DataExportRead } from '../models/DataExportRead';
import type { DataLifecycleEventRead } from '../models/DataLifecycleEventRead';
import type { DataLifecyclePurgeRead } from '../models/DataLifecyclePurgeRead';
import type { DataLifecyclePurgeRequest } from '../models/DataLifecyclePurgeRequest';
import type { DataRetentionPolicyRead } from '../models/DataRetentionPolicyRead';
import type { DataRetentionPolicyUpdate } from '../models/DataRetentionPolicyUpdate';
import type { DeletedSourceAssetRead } from '../models/DeletedSourceAssetRead';
import type { LegalHoldCreate } from '../models/LegalHoldCreate';
import type { LegalHoldRead } from '../models/LegalHoldRead';
import type { LegalHoldRelease } from '../models/LegalHoldRelease';
import type { SourceAssetImpactRead } from '../models/SourceAssetImpactRead';
import type { CancelablePromise } from '../core/CancelablePromise';
import { OpenAPI } from '../core/OpenAPI';
import { request as __request } from '../core/request';
export class CommercialService {
  /**
   * Create Commercial Adjustment
   * @returns CommercialAdjustmentRead Successful Response
   * @throws ApiError
   */
  public static createCommercialAdjustmentApiV1CommercialAdjustmentsPost({
    requestBody,
  }: {
    requestBody: CommercialUsageAdjustmentCreate,
  }): CancelablePromise<CommercialAdjustmentRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/adjustments',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Reverse Commercial Adjustment
   * @returns CommercialAdjustmentRead Successful Response
   * @throws ApiError
   */
  public static reverseCommercialAdjustmentApiV1CommercialAdjustmentsAdjustmentIdReversalPost({
    adjustmentId,
    requestBody,
  }: {
    adjustmentId: string,
    requestBody: CommercialReversalCreate,
  }): CancelablePromise<CommercialAdjustmentRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/adjustments/{adjustment_id}/reversal',
      path: {
        'adjustment_id': adjustmentId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Billing Accounts
   * @returns BillingAccountRead Successful Response
   * @throws ApiError
   */
  public static listBillingAccountsApiV1CommercialBillingAccountsGet({
    limit = 200,
  }: {
    limit?: number,
  }): CancelablePromise<Array<BillingAccountRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/billing-accounts',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Billing Customer Mapping
   * @returns BillingAccountRead Successful Response
   * @throws ApiError
   */
  public static updateBillingCustomerMappingApiV1CommercialBillingAccountsAccountIdProviderMappingPost({
    accountId,
    requestBody,
  }: {
    accountId: string,
    requestBody: BillingCustomerMappingUpdate,
  }): CancelablePromise<BillingAccountRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/billing-accounts/{account_id}/provider-mapping',
      path: {
        'account_id': accountId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Billing Deliveries
   * @returns BillingDeliveryRead Successful Response
   * @throws ApiError
   */
  public static listBillingDeliveriesApiV1CommercialBillingDeliveriesGet({
    deliveryState = 'all',
    limit = 200,
  }: {
    deliveryState?: 'all' | 'pending' | 'processing' | 'retry' | 'succeeded' | 'dead',
    limit?: number,
  }): CancelablePromise<Array<BillingDeliveryRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/billing-deliveries',
      query: {
        'delivery_state': deliveryState,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Replay Billing Delivery
   * @returns BillingDeliveryRead Successful Response
   * @throws ApiError
   */
  public static replayBillingDeliveryApiV1CommercialBillingDeliveriesDeliveryIdReplayPost({
    deliveryId,
    requestBody,
  }: {
    deliveryId: string,
    requestBody: BillingDeliveryReplayRequest,
  }): CancelablePromise<BillingDeliveryRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/billing-deliveries/{delivery_id}/replay',
      path: {
        'delivery_id': deliveryId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Billing Disputes
   * @returns BillingDisputeRead Successful Response
   * @throws ApiError
   */
  public static listBillingDisputesApiV1CommercialBillingDisputesGet({
    disputeStatus = 'all',
    limit = 200,
  }: {
    disputeStatus?: 'all' | 'open' | 'investigating' | 'resolved' | 'rejected' | 'cancelled',
    limit?: number,
  }): CancelablePromise<Array<BillingDisputeRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/billing-disputes',
      query: {
        'dispute_status': disputeStatus,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Create Billing Dispute
   * @returns BillingDisputeRead Successful Response
   * @throws ApiError
   */
  public static createBillingDisputeApiV1CommercialBillingDisputesPost({
    requestBody,
  }: {
    requestBody: BillingDisputeCreate,
  }): CancelablePromise<BillingDisputeRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/billing-disputes',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Transition Billing Dispute
   * @returns BillingDisputeRead Successful Response
   * @throws ApiError
   */
  public static transitionBillingDisputeApiV1CommercialBillingDisputesDisputeIdTransitionPost({
    disputeId,
    requestBody,
  }: {
    disputeId: string,
    requestBody: BillingDisputeTransition,
  }): CancelablePromise<BillingDisputeRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/billing-disputes/{dispute_id}/transition',
      path: {
        'dispute_id': disputeId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Commercial Clients
   * @returns CommercialClientRead Successful Response
   * @throws ApiError
   */
  public static listCommercialClientsApiV1CommercialClientsGet({
    limit = 200,
  }: {
    limit?: number,
  }): CancelablePromise<Array<CommercialClientRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/clients',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Update Commercial Client Status
   * @returns CommercialClientRead Successful Response
   * @throws ApiError
   */
  public static updateCommercialClientStatusApiV1CommercialClientsClientIdStatusPost({
    clientId,
    requestBody,
  }: {
    clientId: string,
    requestBody: CommercialClientStatusUpdate,
  }): CancelablePromise<CommercialClientRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/clients/{client_id}/status',
      path: {
        'client_id': clientId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Data Lifecycle Events
   * @returns DataLifecycleEventRead Successful Response
   * @throws ApiError
   */
  public static listDataLifecycleEventsApiV1CommercialDataLifecycleEventsGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<DataLifecycleEventRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/events',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Export Purge Candidates
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static listExportPurgeCandidatesApiV1CommercialDataLifecycleExportCandidatesGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<DataExportRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/export-candidates',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Purge Export Artifacts
   * @returns DataLifecyclePurgeRead Successful Response
   * @throws ApiError
   */
  public static purgeExportArtifactsApiV1CommercialDataLifecycleExportsJobIdPurgePost({
    jobId,
    requestBody,
  }: {
    jobId: string,
    requestBody: DataLifecyclePurgeRequest,
  }): CancelablePromise<DataLifecyclePurgeRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/data-lifecycle/exports/{job_id}/purge',
      path: {
        'job_id': jobId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Legal Holds
   * @returns LegalHoldRead Successful Response
   * @throws ApiError
   */
  public static listLegalHoldsApiV1CommercialDataLifecycleLegalHoldsGet({
    activeOnly = false,
  }: {
    activeOnly?: boolean,
  }): CancelablePromise<Array<LegalHoldRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/legal-holds',
      query: {
        'active_only': activeOnly,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Place Legal Hold
   * @returns LegalHoldRead Successful Response
   * @throws ApiError
   */
  public static placeLegalHoldApiV1CommercialDataLifecycleLegalHoldsPost({
    requestBody,
  }: {
    requestBody: LegalHoldCreate,
  }): CancelablePromise<LegalHoldRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/data-lifecycle/legal-holds',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Release Legal Hold
   * @returns LegalHoldRead Successful Response
   * @throws ApiError
   */
  public static releaseLegalHoldApiV1CommercialDataLifecycleLegalHoldsHoldIdReleasePost({
    holdId,
    requestBody,
  }: {
    holdId: string,
    requestBody: LegalHoldRelease,
  }): CancelablePromise<LegalHoldRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/data-lifecycle/legal-holds/{hold_id}/release',
      path: {
        'hold_id': holdId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Data Retention Policies
   * @returns DataRetentionPolicyRead Successful Response
   * @throws ApiError
   */
  public static listDataRetentionPoliciesApiV1CommercialDataLifecycleRetentionPoliciesGet(): CancelablePromise<Array<DataRetentionPolicyRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/retention-policies',
    });
  }
  /**
   * Upsert Export Retention Policy
   * @returns DataRetentionPolicyRead Successful Response
   * @throws ApiError
   */
  public static upsertExportRetentionPolicyApiV1CommercialDataLifecycleRetentionPoliciesExportArtifactsPut({
    requestBody,
  }: {
    requestBody: DataRetentionPolicyUpdate,
  }): CancelablePromise<DataRetentionPolicyRead> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/commercial/data-lifecycle/retention-policies/export-artifacts',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Upsert Source Retention Policy
   * @returns DataRetentionPolicyRead Successful Response
   * @throws ApiError
   */
  public static upsertSourceRetentionPolicyApiV1CommercialDataLifecycleRetentionPoliciesSourceAssetsPut({
    requestBody,
  }: {
    requestBody: DataRetentionPolicyUpdate,
  }): CancelablePromise<DataRetentionPolicyRead> {
    return __request(OpenAPI, {
      method: 'PUT',
      url: '/api/v1/commercial/data-lifecycle/retention-policies/source-assets',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Deleted Source Assets
   * @returns DeletedSourceAssetRead Successful Response
   * @throws ApiError
   */
  public static listDeletedSourceAssetsApiV1CommercialDataLifecycleSourceAssetsDeletedGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<DeletedSourceAssetRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/source-assets/deleted',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Get Source Asset Purge Impact
   * @returns SourceAssetImpactRead Successful Response
   * @throws ApiError
   */
  public static getSourceAssetPurgeImpactApiV1CommercialDataLifecycleSourceAssetsAssetIdImpactGet({
    assetId,
  }: {
    assetId: string,
  }): CancelablePromise<SourceAssetImpactRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/impact',
      path: {
        'asset_id': assetId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Purge Source Asset
   * @returns DataLifecyclePurgeRead Successful Response
   * @throws ApiError
   */
  public static purgeSourceAssetApiV1CommercialDataLifecycleSourceAssetsAssetIdPurgePost({
    assetId,
    requestBody,
  }: {
    assetId: string,
    requestBody: DataLifecyclePurgeRequest,
  }): CancelablePromise<DataLifecyclePurgeRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/purge',
      path: {
        'asset_id': assetId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Reauthorize Source Asset
   * @returns DataLifecyclePurgeRead Successful Response
   * @throws ApiError
   */
  public static reauthorizeSourceAssetApiV1CommercialDataLifecycleSourceAssetsAssetIdReauthorizePost({
    assetId,
    requestBody,
  }: {
    assetId: string,
    requestBody: DataLifecyclePurgeRequest,
  }): CancelablePromise<DataLifecyclePurgeRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/data-lifecycle/source-assets/{asset_id}/reauthorize',
      path: {
        'asset_id': assetId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Source Purge Candidates
   * @returns SourceAssetImpactRead Successful Response
   * @throws ApiError
   */
  public static listSourcePurgeCandidatesApiV1CommercialDataLifecycleSourceCandidatesGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<SourceAssetImpactRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/data-lifecycle/source-candidates',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Data Exports
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static listDataExportsApiV1CommercialExportsGet({
    limit = 100,
  }: {
    limit?: number,
  }): CancelablePromise<Array<DataExportRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/exports',
      query: {
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Approve Data Export
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static approveDataExportApiV1CommercialExportsJobIdApprovePost({
    jobId,
  }: {
    jobId: string,
  }): CancelablePromise<DataExportRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/exports/{job_id}/approve',
      path: {
        'job_id': jobId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Cancel Data Export As Operator
   * @returns DataExportRead Successful Response
   * @throws ApiError
   */
  public static cancelDataExportAsOperatorApiV1CommercialExportsJobIdCancelPost({
    jobId,
  }: {
    jobId: string,
  }): CancelablePromise<DataExportRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/exports/{job_id}/cancel',
      path: {
        'job_id': jobId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Read Commercial Overview
   * @returns CommercialOverviewRead Successful Response
   * @throws ApiError
   */
  public static readCommercialOverviewApiV1CommercialOverviewGet(): CancelablePromise<CommercialOverviewRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/overview',
    });
  }
  /**
   * Reconcile Commercial Subscription
   * @returns CommercialReconciliationRead Successful Response
   * @throws ApiError
   */
  public static reconcileCommercialSubscriptionApiV1CommercialReconciliationsPost({
    requestBody,
  }: {
    requestBody: CommercialReconciliationCreate,
  }): CancelablePromise<CommercialReconciliationRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/reconciliations',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Expire Commercial Reservations
   * @returns CommercialExpirationRead Successful Response
   * @throws ApiError
   */
  public static expireCommercialReservationsApiV1CommercialReservationsExpirePost({
    requestBody,
  }: {
    requestBody: CommercialExpirationRequest,
  }): CancelablePromise<CommercialExpirationRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/reservations/expire',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * List Commercial Risk Events
   * @returns CommercialRiskEventRead Successful Response
   * @throws ApiError
   */
  public static listCommercialRiskEventsApiV1CommercialRiskEventsGet({
    caseStatus = 'all',
    limit = 200,
  }: {
    caseStatus?: 'all' | 'open' | 'acknowledged' | 'resolved' | 'dismissed',
    limit?: number,
  }): CancelablePromise<Array<CommercialRiskEventRead>> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/risk-events',
      query: {
        'case_status': caseStatus,
        'limit': limit,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Page Commercial Risk Events
   * @returns CommercialRiskEventPageRead Successful Response
   * @throws ApiError
   */
  public static pageCommercialRiskEventsApiV1CommercialRiskEventsPageGet({
    caseStatus = 'all',
    limit = 25,
    cursor,
  }: {
    caseStatus?: 'all' | 'open' | 'acknowledged' | 'resolved' | 'dismissed',
    limit?: number,
    cursor?: (string | null),
  }): CancelablePromise<CommercialRiskEventPageRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/risk-events/page',
      query: {
        'case_status': caseStatus,
        'limit': limit,
        'cursor': cursor,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Review Commercial Risk Event
   * @returns CommercialRiskEventRead Successful Response
   * @throws ApiError
   */
  public static reviewCommercialRiskEventApiV1CommercialRiskEventsEventIdReviewPost({
    eventId,
    requestBody,
  }: {
    eventId: string,
    requestBody: CommercialRiskReview,
  }): CancelablePromise<CommercialRiskEventRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/risk-events/{event_id}/review',
      path: {
        'event_id': eventId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Reverse Commercial Settlement
   * @returns CommercialAdjustmentRead Successful Response
   * @throws ApiError
   */
  public static reverseCommercialSettlementApiV1CommercialSettlementsSettlementIdReversalPost({
    settlementId,
    requestBody,
  }: {
    settlementId: string,
    requestBody: CommercialReversalCreate,
  }): CancelablePromise<CommercialAdjustmentRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/settlements/{settlement_id}/reversal',
      path: {
        'settlement_id': settlementId,
      },
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Create Billing Statement
   * @returns BillingStatementRead Successful Response
   * @throws ApiError
   */
  public static createBillingStatementApiV1CommercialStatementsPost({
    requestBody,
  }: {
    requestBody: BillingStatementCreate,
  }): CancelablePromise<BillingStatementRead> {
    return __request(OpenAPI, {
      method: 'POST',
      url: '/api/v1/commercial/statements',
      body: requestBody,
      mediaType: 'application/json',
      errors: {
        422: `Validation Error`,
      },
    });
  }
  /**
   * Read Billing Statement
   * @returns BillingStatementRead Successful Response
   * @throws ApiError
   */
  public static readBillingStatementApiV1CommercialStatementsStatementIdGet({
    statementId,
  }: {
    statementId: string,
  }): CancelablePromise<BillingStatementRead> {
    return __request(OpenAPI, {
      method: 'GET',
      url: '/api/v1/commercial/statements/{statement_id}',
      path: {
        'statement_id': statementId,
      },
      errors: {
        422: `Validation Error`,
      },
    });
  }
}
