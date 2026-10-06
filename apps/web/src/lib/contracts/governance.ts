import { contractRequest } from "../contract";
import type {
  DataQualityCoverageRead,
  DataQualityIssueActionRequest,
  DataQualityIssueEventRead,
  DataQualityIssueRead,
  DataQualityOwnerRead,
  DataQualitySnapshotRead,
  EntityResolutionCaseRead,
  EntityResolutionImpactRead,
  GovernanceFactComparisonRead,
  GovernanceRunPageRead,
  ProjectionMaintenanceJobRead,
  PublicationBatchRead,
  RunState,
  StagedFactRead,
} from "../generated";
import { GovernanceService } from "../generated";

export const governanceKeys = {
  queues: ["governance", "queues"] as const,
  factComparison: (factId: string) => ["governance", "fact-comparison", factId] as const,
  identityHistory: ["governance", "identity-history"] as const,
  identityImpact: (caseId: string) => ["governance", "identity-impact", caseId] as const,
  qualityIssues: (status: string) => ["governance", "quality-issues", status] as const,
  qualityIssueEvents: (issueId: string) => ["governance", "quality-issue-events", issueId] as const,
  qualityOwners: ["governance", "quality-owners"] as const,
  qualitySnapshots: ["governance", "quality-snapshots"] as const,
  qualityCoverage: ["governance", "quality-coverage"] as const,
  publicationBatches: ["governance", "publication-batches"] as const,
  publicationBatch: (batchId: string) => ["governance", "publication-batch", batchId] as const,
  projectionMaintenanceAccess: ["governance", "projection-maintenance-access"] as const,
  projectionMaintenanceJobs: ["governance", "projection-maintenance-jobs"] as const,
  runs: (status: RunState | "all", limit: number, offset: number) =>
    ["governance", "runs", status, limit, offset] as const,
};

export type GovernanceQueues = {
  facts: StagedFactRead[];
  identityCases: EntityResolutionCaseRead[];
};

export function loadFactComparison(factId: string, signal?: AbortSignal): Promise<GovernanceFactComparisonRead> {
  return contractRequest(
    GovernanceService.getStagedFactComparisonApiV1GovernanceStagedFactsStagedFactIdComparisonGet({
      stagedFactId: factId,
    }),
    signal,
  );
}

export async function loadGovernanceQueues(signal?: AbortSignal): Promise<GovernanceQueues> {
  const [facts, identityCases] = await Promise.all([
    contractRequest(GovernanceService.listReviewQueueApiV1GovernanceReviewQueueGet({ limit: 500 }), signal),
    contractRequest(
      GovernanceService.listEntityResolutionCasesApiV1GovernanceEntityResolutionCasesGet({
        status: "pending",
        limit: 500,
      }),
      signal,
    ),
  ]);
  return { facts, identityCases };
}

export function loadGovernanceRuns(
  status: RunState | "all",
  limit: number,
  offset: number,
  signal?: AbortSignal,
): Promise<GovernanceRunPageRead> {
  return contractRequest(
    GovernanceService.listGovernanceRunsApiV1GovernanceRunsGet({
      status: status === "all" ? null : status,
      limit,
      offset,
    }),
    signal,
  );
}

export async function loadEntityResolutionHistory(signal?: AbortSignal): Promise<EntityResolutionCaseRead[]> {
  const statuses = ["approved", "reverted", "rejected"] as const;
  const pages = await Promise.all(
    statuses.map((status) =>
      contractRequest(
        GovernanceService.listEntityResolutionCasesApiV1GovernanceEntityResolutionCasesGet({
          status,
          limit: 500,
        }),
        signal,
      ),
    ),
  );
  return pages
    .flat()
    .sort((left, right) => right.updated_at.localeCompare(left.updated_at) || left.id.localeCompare(right.id));
}

export function loadEntityResolutionImpact(caseId: string, signal?: AbortSignal): Promise<EntityResolutionImpactRead> {
  return contractRequest(
    GovernanceService.getEntityResolutionCaseImpactApiV1GovernanceEntityResolutionCasesCaseIdImpactGet({ caseId }),
    signal,
  );
}

export function decideStagedFact({
  stagedFactId,
  decision,
  notes,
}: {
  stagedFactId: string;
  decision: "approve" | "reject";
  notes: string;
}): Promise<StagedFactRead> {
  return contractRequest(
    GovernanceService.decideStagedFactApiV1GovernanceStagedFactsStagedFactIdDecisionPost({
      stagedFactId,
      requestBody: { decision, notes: notes.trim() || null },
    }),
  );
}

export function loadPublicationBatches(signal?: AbortSignal): Promise<PublicationBatchRead[]> {
  return contractRequest(
    GovernanceService.listPublicationBatchesApiV1GovernancePublicationBatchesGet({ limit: 100 }),
    signal,
  );
}

export function loadPublicationBatch(batchId: string, signal?: AbortSignal): Promise<PublicationBatchRead> {
  return contractRequest(
    GovernanceService.getPublicationBatchApiV1GovernancePublicationBatchesBatchIdGet({ batchId }),
    signal,
  );
}

export function previewPublicationBatch({
  operation,
  stagedFactIds,
  idempotencyKey,
  reason,
}: {
  operation: "publish" | "withdraw";
  stagedFactIds: string[];
  idempotencyKey: string;
  reason: string;
}): Promise<PublicationBatchRead> {
  return contractRequest(
    GovernanceService.previewPublicationBatchApiV1GovernancePublicationBatchesPreviewPost({
      requestBody: {
        operation,
        staged_fact_ids: stagedFactIds,
        idempotency_key: idempotencyKey,
        reason: reason.trim() || null,
      },
    }),
  );
}

export function commitPublicationBatch({
  batchId,
  previewSha256,
}: {
  batchId: string;
  previewSha256: string;
}): Promise<PublicationBatchRead> {
  return contractRequest(
    GovernanceService.commitPublicationBatchApiV1GovernancePublicationBatchesBatchIdCommitPost({
      batchId,
      requestBody: { preview_sha256: previewSha256 },
    }),
  );
}

export function loadProjectionMaintenanceJobs(signal?: AbortSignal): Promise<ProjectionMaintenanceJobRead[]> {
  return contractRequest(
    GovernanceService.listProjectionMaintenanceJobsApiV1GovernanceProjectionMaintenanceJobsGet({ limit: 100 }),
    signal,
  );
}

export async function loadProjectionMaintenanceAccess(signal?: AbortSignal): Promise<boolean> {
  const access = await contractRequest(
    GovernanceService.getProjectionMaintenanceAccessApiV1GovernanceProjectionMaintenanceAccessGet(),
    signal,
  );
  return access.allowed;
}

export function requestProjectionMaintenance(
  operation: "consistency_check" | "rebuild",
): Promise<ProjectionMaintenanceJobRead> {
  return contractRequest(
    GovernanceService.requestProjectionMaintenanceJobApiV1GovernanceProjectionMaintenanceJobsPost({
      requestBody: { operation },
    }),
  );
}

export function loadDataQualitySnapshots(signal?: AbortSignal): Promise<DataQualitySnapshotRead[]> {
  return contractRequest(
    GovernanceService.listDataQualitySnapshotsApiV1GovernanceQualitySnapshotsGet({ limit: 90 }),
    signal,
  );
}

export function loadDataQualityCoverage(signal?: AbortSignal): Promise<DataQualityCoverageRead[]> {
  return contractRequest(
    GovernanceService.listDataQualityCoverageApiV1GovernanceQualityCoverageGet({ limit: 100 }),
    signal,
  );
}

export function evaluateDataQuality(): Promise<DataQualitySnapshotRead> {
  return contractRequest(GovernanceService.evaluateDataQualityApiV1GovernanceQualityEvaluationsPost());
}

export function loadDataQualityOwners(signal?: AbortSignal): Promise<DataQualityOwnerRead[]> {
  return contractRequest(GovernanceService.listDataQualityOwnersApiV1GovernanceQualityOwnersGet(), signal);
}

export function loadDataQualityIssues(status: string, signal?: AbortSignal): Promise<DataQualityIssueRead[]> {
  return contractRequest(
    GovernanceService.listDataQualityIssuesApiV1GovernanceQualityIssuesGet({
      status: status === "all" ? null : (status as DataQualityIssueRead["status"]),
      limit: 500,
    }),
    signal,
  );
}

export function loadDataQualityIssueEvents(
  issueId: string,
  signal?: AbortSignal,
): Promise<DataQualityIssueEventRead[]> {
  return contractRequest(
    GovernanceService.listDataQualityIssueEventsApiV1GovernanceQualityIssuesIssueIdEventsGet({ issueId }),
    signal,
  );
}

export function actOnDataQualityIssue({
  issueId,
  ...requestBody
}: DataQualityIssueActionRequest & { issueId: string }): Promise<DataQualityIssueRead> {
  return contractRequest(
    GovernanceService.actOnDataQualityIssueApiV1GovernanceQualityIssuesIssueIdActionsPost({
      issueId,
      requestBody,
    }),
  );
}

export function decideEntityResolution({
  caseId,
  action,
  expectedStatus,
  canonicalEntityId,
  notes,
}: {
  caseId: string;
  action: "approve" | "reject" | "revert";
  expectedStatus: EntityResolutionCaseRead["status"];
  canonicalEntityId: string | null;
  notes: string;
}): Promise<EntityResolutionCaseRead> {
  return contractRequest(
    GovernanceService.decideEntityResolutionCaseApiV1GovernanceEntityResolutionCasesCaseIdDecisionPost({
      caseId,
      requestBody: {
        action,
        expected_status: expectedStatus,
        canonical_entity_id: canonicalEntityId,
        notes: notes.trim() || null,
      },
    }),
  );
}

export type StagedFact = StagedFactRead;
export type EntityResolutionCase = EntityResolutionCaseRead;
export type EntityResolutionImpact = EntityResolutionImpactRead;
export type GovernanceRun = GovernanceRunPageRead["items"][number];
export type GovernanceRunStatus = RunState;
export type PublicationBatch = PublicationBatchRead;
export type ProjectionMaintenanceJob = ProjectionMaintenanceJobRead;
export type DataQualitySnapshot = DataQualitySnapshotRead;
export type DataQualityCoverage = DataQualityCoverageRead;
export type DataQualityIssue = DataQualityIssueRead;
export type DataQualityOwner = DataQualityOwnerRead;
