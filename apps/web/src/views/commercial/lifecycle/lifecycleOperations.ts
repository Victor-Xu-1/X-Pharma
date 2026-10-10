import type {
  DataExportJob,
  DeletedSourceAsset,
  LegalHold,
  SourceAssetImpact,
} from "../../../lib/contracts/commercial";
import type { CommercialOperationRunner } from "../types";
import type { LegalHoldInput } from "./LegalHoldForm";
import type { RetentionPolicyInput } from "./RetentionPolicyForm";

/** Payload construction only: never starts an alternate mutation or authorization chain. */
export function lifecycleOperations(runOperation: CommercialOperationRunner) {
  function saveRetentionPolicy(input: RetentionPolicyInput) {
    return runOperation(
      "lifecycle:policy:" + input.dataClass,
      {
        kind: "save-retention-policy",
        dataClass: input.dataClass,
        requestBody: {
          retention_seconds: input.retentionSeconds,
          legal_basis: input.legalBasis,
          geographic_scope: input.geographicScope,
          active: input.active,
        },
      },
      "保留策略保存失败",
    );
  }
  function placeLegalHold(input: LegalHoldInput) {
    return runOperation(
      "lifecycle:hold",
      {
        kind: "place-legal-hold",
        requestBody: {
          scope_type: input.scopeType,
          scope_id: input.scopeId,
          matter_reference: input.matterReference,
          reason: input.reason,
        },
      },
      "Legal hold 创建失败",
    );
  }
  function releaseLegalHold(hold: LegalHold, reason: string) {
    return runOperation(
      "lifecycle:hold:" + hold.id,
      { kind: "release-legal-hold", holdId: hold.id, requestBody: { reason } },
      "Legal hold 解除失败",
    );
  }
  function purgeExport(job: DataExportJob, reason: string, key: string) {
    return runOperation(
      "lifecycle:purge:" + job.id,
      { kind: "purge-export", jobId: job.id, requestBody: { idempotency_key: key, reason } },
      "导出对象清除失败",
    );
  }
  function purgeSourceAsset(asset: SourceAssetImpact, reason: string, key: string) {
    return runOperation(
      "lifecycle:source-purge:" + asset.id,
      { kind: "purge-source", assetId: asset.id, requestBody: { idempotency_key: key, reason } },
      "源资料清除失败",
    );
  }
  function reauthorizeSourceAsset(asset: DeletedSourceAsset, reason: string, key: string) {
    return runOperation(
      "lifecycle:source-reauthorize:" + asset.id,
      { kind: "reauthorize-source", assetId: asset.id, requestBody: { idempotency_key: key, reason } },
      "源资料重新授权失败",
    );
  }
  return {
    saveRetentionPolicy,
    placeLegalHold,
    releaseLegalHold,
    purgeExport,
    purgeSourceAsset,
    reauthorizeSourceAsset,
  };
}
