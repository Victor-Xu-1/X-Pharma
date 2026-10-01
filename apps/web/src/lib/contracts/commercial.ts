import { contractRequest } from "../contract";
import type {
  BillingAccountRead,
  BillingCustomerMappingUpdate,
  BillingDeliveryRead,
  BillingDeliveryReplayRequest,
  BillingDisputeCreate,
  BillingDisputeRead,
  BillingDisputeTransition,
  CommercialClientRead,
  CommercialClientStatusUpdate,
  CommercialOverviewRead,
  CommercialRiskEventPageRead,
  CommercialRiskEventRead,
  CommercialRiskReview,
  DataExportRead,
  DataLifecycleEventRead,
  DataLifecyclePurgeRequest,
  DataRetentionPolicyRead,
  DataRetentionPolicyUpdate,
  DeletedSourceAssetRead,
  LegalHoldCreate,
  LegalHoldRead,
  LegalHoldRelease,
  SourceAssetImpactRead,
} from "../generated";
import { CommercialService } from "../generated";

export type BillingDeliveryFilter = "all" | BillingDeliveryRead["state"];
export type BillingDisputeFilter = "all" | BillingDisputeRead["status"];
export type CommercialRiskFilter = "all" | CommercialRiskEventRead["case_status"];

export const commercialKeys = {
  root: ["commercial"] as const,
  overview: ["commercial", "overview"] as const,
  clients: ["commercial", "clients"] as const,
  billing: (deliveryFilter: BillingDeliveryFilter) => ["commercial", "billing", { deliveryFilter }] as const,
  disputes: (disputeFilter: BillingDisputeFilter) => ["commercial", "disputes", { disputeFilter }] as const,
  exports: ["commercial", "exports"] as const,
  risks: (caseStatus: CommercialRiskFilter, cursor: string | null) =>
    ["commercial", "risks", { caseStatus, cursor }] as const,
  lifecycle: ["commercial", "lifecycle"] as const,
};

export function loadCommercialOverview(signal?: AbortSignal): Promise<CommercialOverviewRead> {
  return contractRequest(CommercialService.readCommercialOverviewApiV1CommercialOverviewGet(), signal);
}

export function loadCommercialClients(signal?: AbortSignal): Promise<CommercialClientRead[]> {
  return contractRequest(CommercialService.listCommercialClientsApiV1CommercialClientsGet({ limit: 200 }), signal);
}

export async function loadCommercialBilling(deliveryFilter: BillingDeliveryFilter, signal?: AbortSignal) {
  const [accounts, deliveries] = await Promise.all([
    contractRequest(CommercialService.listBillingAccountsApiV1CommercialBillingAccountsGet({ limit: 200 }), signal),
    contractRequest(
      CommercialService.listBillingDeliveriesApiV1CommercialBillingDeliveriesGet({
        deliveryState: deliveryFilter,
        limit: 200,
      }),
      signal,
    ),
  ]);
  return { accounts, deliveries };
}

export function loadCommercialDisputes(
  disputeFilter: BillingDisputeFilter,
  signal?: AbortSignal,
): Promise<BillingDisputeRead[]> {
  return contractRequest(
    CommercialService.listBillingDisputesApiV1CommercialBillingDisputesGet({
      disputeStatus: disputeFilter,
      limit: 200,
    }),
    signal,
  );
}

export function loadCommercialExports(signal?: AbortSignal): Promise<DataExportRead[]> {
  return contractRequest(CommercialService.listDataExportsApiV1CommercialExportsGet({ limit: 100 }), signal);
}

export async function loadCommercialRiskPage(
  caseStatus: CommercialRiskFilter,
  cursor: string | null,
  signal?: AbortSignal,
): Promise<CommercialRiskEventPageRead> {
  return contractRequest(
    CommercialService.pageCommercialRiskEventsApiV1CommercialRiskEventsPageGet({
      caseStatus,
      limit: 25,
      cursor,
    }),
    signal,
  );
}

export type LifecycleWorkspace = {
  retentionPolicies: DataRetentionPolicyRead[];
  legalHolds: LegalHoldRead[];
  lifecycleEvents: DataLifecycleEventRead[];
  purgeCandidates: DataExportRead[];
  sourcePurgeCandidates: SourceAssetImpactRead[];
  deletedSourceAssets: DeletedSourceAssetRead[];
};

export async function loadLifecycleWorkspace(signal?: AbortSignal): Promise<LifecycleWorkspace> {
  const [retentionPolicies, legalHolds, lifecycleEvents, deletedSourceAssets] = await Promise.all([
    contractRequest(
      CommercialService.listDataRetentionPoliciesApiV1CommercialDataLifecycleRetentionPoliciesGet(),
      signal,
    ),
    contractRequest(
      CommercialService.listLegalHoldsApiV1CommercialDataLifecycleLegalHoldsGet({ activeOnly: false }),
      signal,
    ),
    contractRequest(
      CommercialService.listDataLifecycleEventsApiV1CommercialDataLifecycleEventsGet({ limit: 100 }),
      signal,
    ),
    contractRequest(
      CommercialService.listDeletedSourceAssetsApiV1CommercialDataLifecycleSourceAssetsDeletedGet({ limit: 100 }),
      signal,
    ),
  ]);
  const exportPolicyActive = retentionPolicies.some(
    (policy) => policy.active && policy.data_class === "commercial_export_artifact",
  );
  const sourcePolicyActive = retentionPolicies.some(
    (policy) => policy.active && policy.data_class === "source_asset_snapshot",
  );
  const [purgeCandidates, sourcePurgeCandidates] = await Promise.all([
    exportPolicyActive
      ? contractRequest(
          CommercialService.listExportPurgeCandidatesApiV1CommercialDataLifecycleExportCandidatesGet({ limit: 100 }),
          signal,
        )
      : Promise.resolve([]),
    sourcePolicyActive
      ? contractRequest(
          CommercialService.listSourcePurgeCandidatesApiV1CommercialDataLifecycleSourceCandidatesGet({ limit: 100 }),
          signal,
        )
      : Promise.resolve([]),
  ]);
  return {
    retentionPolicies,
    legalHolds,
    lifecycleEvents,
    purgeCandidates,
    sourcePurgeCandidates,
    deletedSourceAssets,
  };
}

export function createBillingDispute(requestBody: BillingDisputeCreate): Promise<BillingDisputeRead> {
  return contractRequest(CommercialService.createBillingDisputeApiV1CommercialBillingDisputesPost({ requestBody }));
}

export function transitionBillingDispute(
  disputeId: string,
  requestBody: BillingDisputeTransition,
): Promise<BillingDisputeRead> {
  return contractRequest(
    CommercialService.transitionBillingDisputeApiV1CommercialBillingDisputesDisputeIdTransitionPost({
      disputeId,
      requestBody,
    }),
  );
}

export function updateBillingCustomerMapping(
  accountId: string,
  requestBody: BillingCustomerMappingUpdate,
): Promise<BillingAccountRead> {
  return contractRequest(
    CommercialService.updateBillingCustomerMappingApiV1CommercialBillingAccountsAccountIdProviderMappingPost({
      accountId,
      requestBody,
    }),
  );
}

export function replayBillingDelivery(
  deliveryId: string,
  requestBody: BillingDeliveryReplayRequest,
): Promise<BillingDeliveryRead> {
  return contractRequest(
    CommercialService.replayBillingDeliveryApiV1CommercialBillingDeliveriesDeliveryIdReplayPost({
      deliveryId,
      requestBody,
    }),
  );
}

export function updateCommercialClientStatus(
  clientId: string,
  requestBody: CommercialClientStatusUpdate,
): Promise<CommercialClientRead> {
  return contractRequest(
    CommercialService.updateCommercialClientStatusApiV1CommercialClientsClientIdStatusPost({ clientId, requestBody }),
  );
}

export function actOnDataExport(jobId: string, action: "approve" | "cancel"): Promise<DataExportRead> {
  return action === "approve"
    ? contractRequest(CommercialService.approveDataExportApiV1CommercialExportsJobIdApprovePost({ jobId }))
    : contractRequest(CommercialService.cancelDataExportAsOperatorApiV1CommercialExportsJobIdCancelPost({ jobId }));
}

export function reviewCommercialRisk(
  eventId: string,
  requestBody: CommercialRiskReview,
): Promise<CommercialRiskEventRead> {
  return contractRequest(
    CommercialService.reviewCommercialRiskEventApiV1CommercialRiskEventsEventIdReviewPost({ eventId, requestBody }),
  );
}

export function saveRetentionPolicy(
  dataClass: DataRetentionPolicyRead["data_class"],
  requestBody: DataRetentionPolicyUpdate,
): Promise<DataRetentionPolicyRead> {
  return dataClass === "source_asset_snapshot"
    ? contractRequest(
        CommercialService.upsertSourceRetentionPolicyApiV1CommercialDataLifecycleRetentionPoliciesSourceAssetsPut({
          requestBody,
        }),
      )
    : contractRequest(
        CommercialService.upsertExportRetentionPolicyApiV1CommercialDataLifecycleRetentionPoliciesExportArtifactsPut({
          requestBody,
        }),
      );
}

export function placeLegalHold(requestBody: LegalHoldCreate): Promise<LegalHoldRead> {
  return contractRequest(CommercialService.placeLegalHoldApiV1CommercialDataLifecycleLegalHoldsPost({ requestBody }));
}

export function releaseLegalHold(holdId: string, requestBody: LegalHoldRelease): Promise<LegalHoldRead> {
  return contractRequest(
    CommercialService.releaseLegalHoldApiV1CommercialDataLifecycleLegalHoldsHoldIdReleasePost({ holdId, requestBody }),
  );
}

export function purgeExportArtifacts(jobId: string, requestBody: DataLifecyclePurgeRequest): Promise<unknown> {
  return contractRequest(
    CommercialService.purgeExportArtifactsApiV1CommercialDataLifecycleExportsJobIdPurgePost({ jobId, requestBody }),
  );
}

export function purgeSourceAsset(assetId: string, requestBody: DataLifecyclePurgeRequest): Promise<unknown> {
  return contractRequest(
    CommercialService.purgeSourceAssetApiV1CommercialDataLifecycleSourceAssetsAssetIdPurgePost({
      assetId,
      requestBody,
    }),
  );
}

export function reauthorizeSourceAsset(assetId: string, requestBody: DataLifecyclePurgeRequest): Promise<unknown> {
  return contractRequest(
    CommercialService.reauthorizeSourceAssetApiV1CommercialDataLifecycleSourceAssetsAssetIdReauthorizePost({
      assetId,
      requestBody,
    }),
  );
}

export type CommercialOperation =
  | { kind: "create-dispute"; requestBody: BillingDisputeCreate }
  | { kind: "transition-dispute"; disputeId: string; requestBody: BillingDisputeTransition }
  | { kind: "update-customer-mapping"; accountId: string; requestBody: BillingCustomerMappingUpdate }
  | { kind: "replay-delivery"; deliveryId: string; requestBody: BillingDeliveryReplayRequest }
  | { kind: "update-client"; clientId: string; requestBody: CommercialClientStatusUpdate }
  | { kind: "act-on-export"; jobId: string; action: "approve" | "cancel" }
  | { kind: "review-risk"; eventId: string; requestBody: CommercialRiskReview }
  | {
      kind: "save-retention-policy";
      dataClass: DataRetentionPolicyRead["data_class"];
      requestBody: DataRetentionPolicyUpdate;
    }
  | { kind: "place-legal-hold"; requestBody: LegalHoldCreate }
  | { kind: "release-legal-hold"; holdId: string; requestBody: LegalHoldRelease }
  | { kind: "purge-export"; jobId: string; requestBody: DataLifecyclePurgeRequest }
  | { kind: "purge-source"; assetId: string; requestBody: DataLifecyclePurgeRequest }
  | { kind: "reauthorize-source"; assetId: string; requestBody: DataLifecyclePurgeRequest };

export function executeCommercialOperation(operation: CommercialOperation): Promise<unknown> {
  switch (operation.kind) {
    case "create-dispute":
      return createBillingDispute(operation.requestBody);
    case "transition-dispute":
      return transitionBillingDispute(operation.disputeId, operation.requestBody);
    case "update-customer-mapping":
      return updateBillingCustomerMapping(operation.accountId, operation.requestBody);
    case "replay-delivery":
      return replayBillingDelivery(operation.deliveryId, operation.requestBody);
    case "update-client":
      return updateCommercialClientStatus(operation.clientId, operation.requestBody);
    case "act-on-export":
      return actOnDataExport(operation.jobId, operation.action);
    case "review-risk":
      return reviewCommercialRisk(operation.eventId, operation.requestBody);
    case "save-retention-policy":
      return saveRetentionPolicy(operation.dataClass, operation.requestBody);
    case "place-legal-hold":
      return placeLegalHold(operation.requestBody);
    case "release-legal-hold":
      return releaseLegalHold(operation.holdId, operation.requestBody);
    case "purge-export":
      return purgeExportArtifacts(operation.jobId, operation.requestBody);
    case "purge-source":
      return purgeSourceAsset(operation.assetId, operation.requestBody);
    case "reauthorize-source":
      return reauthorizeSourceAsset(operation.assetId, operation.requestBody);
  }
}

export type BillingAccount = BillingAccountRead;
export type BillingDelivery = BillingDeliveryRead;
export type BillingDeliveryState = BillingDeliveryRead["state"];
export type BillingDispute = BillingDisputeRead;
export type BillingDisputeAction = BillingDisputeTransition["action"];
export type BillingDisputeCategory = BillingDisputeCreate["category"];
export type BillingDisputeStatus = BillingDisputeRead["status"];
export type CommercialClient = CommercialClientRead;
export type CommercialOverview = CommercialOverviewRead;
export type CommercialRiskEvent = CommercialRiskEventRead;
export type DataExportJob = DataExportRead;
export type DataLifecycleEvent = DataLifecycleEventRead;
export type DataRetentionPolicy = DataRetentionPolicyRead;
export type DeletedSourceAsset = DeletedSourceAssetRead;
export type LegalHold = LegalHoldRead;
export type LegalHoldScope = LegalHoldCreate["scope_type"];
export type RiskCaseStatus = CommercialRiskEventRead["case_status"];
export type SourceAssetImpact = SourceAssetImpactRead;
