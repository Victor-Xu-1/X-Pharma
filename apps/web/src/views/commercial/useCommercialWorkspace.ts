import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useMemo, useState } from "react";
import {
  type BillingDeliveryFilter,
  type BillingDisputeCategory,
  type BillingDisputeFilter,
  type CommercialOperation,
  type CommercialRiskFilter,
  commercialKeys,
  type DataExportJob,
  type DataRetentionPolicy,
  type DeletedSourceAsset,
  type LegalHold,
  type LegalHoldScope,
  loadCommercialBilling,
  loadCommercialClients,
  loadCommercialDisputes,
  loadCommercialExports,
  loadCommercialOverview,
  loadCommercialRiskPage,
  loadLifecycleWorkspace,
  type SourceAssetImpact,
} from "../../lib/contracts/commercial";
import { type commercialWorkspaceMessages, commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { governanceReadDenied } from "../governance/governanceQueryState";
import { sumUnits } from "./format";
import { useLifecycleDrafts } from "./lifecycle/useLifecycleDrafts";
import { useWorkspacePolicyDrafts } from "./policy/useWorkspacePolicy";
import type {
  ClientAction,
  CommercialTab,
  CreateDisputeAction,
  DisputeCaseAction,
  MappingAction,
  ReplayAction,
  RiskAction,
} from "./types";
import { useCommercialOperationBoundary } from "./useCommercialOperationBoundary";

export function useCommercialWorkspace() {
  const queryClient = useQueryClient();

  const [deliveryFilter, setDeliveryFilter] = useState<BillingDeliveryFilter>("all");

  const [disputeFilter, setDisputeFilter] = useState<BillingDisputeFilter>("all");

  const [riskFilter, setRiskFilter] = useState<CommercialRiskFilter>("all");

  const [riskCursor, setRiskCursor] = useState<string | null>(null);

  const [riskCursorHistory, setRiskCursorHistory] = useState<Array<string | null>>([]);

  const [tab, setTab] = useState<CommercialTab>("overview");

  const boundary = useCommercialOperationBoundary();
  const policyDrafts = useWorkspacePolicyDrafts();
  const { busy, actionError, setActionError } = boundary;

  const [clientAction, setClientAction] = useState<ClientAction | null>(null);

  const [riskAction, setRiskAction] = useState<RiskAction | null>(null);

  const [mappingAction, setMappingAction] = useState<MappingAction | null>(null);

  const [replayAction, setReplayAction] = useState<ReplayAction | null>(null);

  const [createDisputeAction, setCreateDisputeAction] = useState<CreateDisputeAction | null>(null);

  const [disputeCaseAction, setDisputeCaseAction] = useState<DisputeCaseAction | null>(null);

  const [externalReference, setExternalReference] = useState("");

  const [reason, setReason] = useState("");

  const [disputeCategory, setDisputeCategory] = useState<BillingDisputeCategory>("usage");

  const [disputedUnits, setDisputedUnits] = useState("");

  const [disputeSubject, setDisputeSubject] = useState("");

  const [assignee, setAssignee] = useState("");

  const [adjustmentKey, setAdjustmentKey] = useState("");

  const commercialQuery = useQuery({
    queryKey: commercialKeys.overview,
    queryFn: ({ signal }) => loadCommercialOverview(signal),
  });

  const clientsQuery = useQuery({
    queryKey: commercialKeys.clients,
    queryFn: ({ signal }) => loadCommercialClients(signal),
    enabled: tab === "clients",
  });
  const billingQuery = useQuery({
    queryKey: commercialKeys.billing(deliveryFilter),
    queryFn: ({ signal }) => loadCommercialBilling(deliveryFilter, signal),
    enabled: tab === "billing",
  });
  const disputesQuery = useQuery({
    queryKey: commercialKeys.disputes(disputeFilter),
    queryFn: ({ signal }) => loadCommercialDisputes(disputeFilter, signal),
    enabled: tab === "disputes",
  });
  const exportsQuery = useQuery({
    queryKey: commercialKeys.exports,
    queryFn: ({ signal }) => loadCommercialExports(signal),
    enabled: tab === "exports",
  });

  const lifecycleQuery = useQuery({
    queryKey: commercialKeys.lifecycle,
    queryFn: ({ signal }) => loadLifecycleWorkspace(signal),
    enabled: tab === "lifecycle",
  });

  const riskQuery = useQuery({
    queryKey: commercialKeys.risks(riskFilter, riskCursor),
    queryFn: ({ signal }) => loadCommercialRiskPage(riskFilter, riskCursor, signal),
    enabled: tab === "risks",
  });

  const overview = governanceReadDenied(commercialQuery.error) ? null : (commercialQuery.data ?? null);
  const clients = governanceReadDenied(clientsQuery.error) ? [] : (clientsQuery.data ?? []);
  const exports = governanceReadDenied(exportsQuery.error) ? [] : (exportsQuery.data ?? []);

  const risks = riskQuery.data?.items ?? [];

  const billingAccounts = billingQuery.data?.accounts ?? [];
  const billingDeliveries = billingQuery.data?.deliveries ?? [];
  const billingDisputes = disputesQuery.data ?? [];

  const retentionPolicies = lifecycleQuery.data?.retentionPolicies ?? [];

  const legalHolds = lifecycleQuery.data?.legalHolds ?? [];

  const lifecycleEvents = lifecycleQuery.data?.lifecycleEvents ?? [];

  const purgeCandidates = lifecycleQuery.data?.purgeCandidates ?? [];

  const sourcePurgeCandidates = lifecycleQuery.data?.sourcePurgeCandidates ?? [];

  const deletedSourceAssets = lifecycleQuery.data?.deletedSourceAssets ?? [];
  const lifecycleDrafts = useLifecycleDrafts(
    retentionPolicies,
    lifecycleQuery.isSuccess && !lifecycleQuery.error && !lifecycleQuery.isFetching,
  );

  async function runOperation(
    busyKey: string,
    operation: CommercialOperation,
    fallback: keyof typeof commercialWorkspaceMessages,
  ): Promise<boolean> {
    const read =
      operation.kind === "update-client"
        ? clientsQuery
        : operation.kind === "transition-dispute"
          ? disputesQuery
          : operation.kind === "review-risk"
            ? riskQuery
            : operation.kind === "act-on-export"
              ? exportsQuery
              : ["create-dispute", "update-customer-mapping", "replay-delivery"].includes(operation.kind)
                ? billingQuery
                : lifecycleQuery;
    if (!read.isSuccess || read.error || read.isFetching) {
      setActionError(t("请先恢复当前记录读取，再提交操作。"));
      return false;
    }
    return boundary.runOperation(busyKey, operation, fallback);
  }

  const metrics = useMemo(
    () => ({
      available: sumUnits(overview?.subscriptions.map((item) => item.available_units) ?? []),
      consumed: sumUnits(overview?.subscriptions.map((item) => item.consumed_units) ?? []),
      activeClients: overview?.active_client_count,
      openRisks: overview?.open_risk_count,
      pendingExports: overview?.pending_export_count,
      deadDeliveries: overview?.dead_billing_delivery_count,
      openDisputes: overview?.open_dispute_count,
    }),
    [overview],
  );

  async function createBillingDispute(event: FormEvent) {
    event.preventDefault();
    if (
      !createDisputeAction ||
      !(Number(disputedUnits) > 0) ||
      disputeSubject.trim().length < 3 ||
      reason.trim().length < 3
    )
      return;
    const succeeded = await runOperation(
      `dispute:create:${createDisputeAction.delivery.statement_id}`,
      {
        kind: "create-dispute",
        requestBody: {
          dispute_key: createDisputeAction.disputeKey,
          statement_id: createDisputeAction.delivery.statement_id,
          invoice_reference_id: null,
          category: disputeCategory,
          disputed_units: disputedUnits,
          subject: disputeSubject.trim(),
          description: reason.trim(),
        },
      },
      "计费争议创建失败",
    );
    if (!succeeded) return;
    setCreateDisputeAction(null);
    setDisputedUnits("");
    setDisputeSubject("");
    setReason("");
  }

  async function transitionBillingDispute(event: FormEvent) {
    event.preventDefault();
    if (!disputeCaseAction || reason.trim().length < 3) return;
    const requiresCredit = disputeCaseAction.action === "resolve_credit";
    if (requiresCredit && (!(Number(disputedUnits) > 0) || adjustmentKey.trim().length < 8)) return;
    const succeeded = await runOperation(
      `dispute:${disputeCaseAction.dispute.id}`,
      {
        kind: "transition-dispute",
        disputeId: disputeCaseAction.dispute.id,
        requestBody: {
          operation_key: disputeCaseAction.operationKey,
          expected_version: disputeCaseAction.dispute.version,
          action: disputeCaseAction.action,
          notes: reason.trim(),
          assigned_to: assignee.trim() || null,
          adjustment_key: requiresCredit ? adjustmentKey.trim() : null,
          credit_units: requiresCredit ? disputedUnits : null,
        },
      },
      "计费争议处理失败",
    );
    if (!succeeded) return;
    setDisputeCaseAction(null);
    setReason("");
    setAssignee("");
    setAdjustmentKey("");
    setDisputedUnits("");
  }

  async function updateCustomerMapping(event: FormEvent) {
    event.preventDefault();
    if (!mappingAction || externalReference.trim().length < 1 || reason.trim().length < 3) return;
    const actionKey = `mapping:${mappingAction.account.id}`;
    const succeeded = await runOperation(
      actionKey,
      {
        kind: "update-customer-mapping",
        accountId: mappingAction.account.id,
        requestBody: { external_customer_reference: externalReference.trim(), reason: reason.trim() },
      },
      "计费账户映射更新失败",
    );
    if (!succeeded) return;
    setMappingAction(null);
    setExternalReference("");
    setReason("");
  }

  async function replayDelivery(event: FormEvent) {
    event.preventDefault();
    if (!replayAction?.delivery.delivery_id || reason.trim().length < 3) return;
    const actionKey = `replay:${replayAction.delivery.delivery_id}`;
    const succeeded = await runOperation(
      actionKey,
      {
        kind: "replay-delivery",
        deliveryId: replayAction.delivery.delivery_id,
        requestBody: { reason: reason.trim() },
      },
      "账单投递重放失败",
    );
    if (!succeeded) return;
    setReplayAction(null);
    setReason("");
  }

  async function updateClient(event: FormEvent) {
    event.preventDefault();
    if (!clientAction || !reason.trim()) return;
    const actionKey = `client:${clientAction.client.id}`;
    const succeeded = await runOperation(
      actionKey,
      {
        kind: "update-client",
        clientId: clientAction.client.id,
        requestBody: { active: clientAction.active, reason: reason.trim() },
      },
      "客户端状态更新失败",
    );
    if (!succeeded) return;
    setClientAction(null);
    setReason("");
  }

  async function actOnExport(job: DataExportJob, action: "approve" | "cancel") {
    const actionKey = `export:${job.id}`;
    await runOperation(actionKey, { kind: "act-on-export", jobId: job.id, action }, "导出任务操作失败");
  }

  async function reviewRisk(event: FormEvent) {
    event.preventDefault();
    if (!riskAction) return;
    const actionKey = `risk:${riskAction.event.id}`;
    const succeeded = await runOperation(
      actionKey,
      {
        kind: "review-risk",
        eventId: riskAction.event.id,
        requestBody: { status: riskAction.status, notes: reason.trim() },
      },
      "风险事件处置失败",
    );
    if (!succeeded) return;
    setRiskAction(null);
    setReason("");
  }

  async function saveRetentionPolicy(input: {
    dataClass: DataRetentionPolicy["data_class"];
    retentionSeconds: number;
    legalBasis: string;
    geographicScope: string[];
    active: boolean;
  }) {
    return runOperation(
      `lifecycle:policy:${input.dataClass}`,
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

  async function placeLegalHold(input: {
    scopeType: LegalHoldScope;
    scopeId: string | null;
    matterReference: string;
    reason: string;
  }) {
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

  async function releaseLegalHold(hold: LegalHold, reason: string) {
    return runOperation(
      `lifecycle:hold:${hold.id}`,
      { kind: "release-legal-hold", holdId: hold.id, requestBody: { reason } },
      "Legal hold 解除失败",
    );
  }

  async function purgeExport(job: DataExportJob, reason: string, key: string) {
    return runOperation(
      `lifecycle:purge:${job.id}`,
      {
        kind: "purge-export",
        jobId: job.id,
        requestBody: { idempotency_key: key, reason },
      },
      "导出对象清除失败",
    );
  }

  async function purgeSourceAsset(asset: SourceAssetImpact, reason: string, key: string) {
    return runOperation(
      `lifecycle:source-purge:${asset.id}`,
      {
        kind: "purge-source",
        assetId: asset.id,
        requestBody: { idempotency_key: key, reason },
      },
      "源资料清除失败",
    );
  }

  async function reauthorizeSourceAsset(asset: DeletedSourceAsset, reason: string, key: string) {
    return runOperation(
      `lifecycle:source-reauthorize:${asset.id}`,
      {
        kind: "reauthorize-source",
        assetId: asset.id,
        requestBody: { idempotency_key: key, reason },
      },
      "源资料重新授权失败",
    );
  }

  const paneQuery =
    tab === "clients"
      ? clientsQuery
      : tab === "billing"
        ? billingQuery
        : tab === "disputes"
          ? disputesQuery
          : tab === "exports"
            ? exportsQuery
            : tab === "risks"
              ? riskQuery
              : tab === "lifecycle"
                ? lifecycleQuery
                : tab === "export-policy"
                  ? null
                  : commercialQuery;
  const paneError = paneQuery?.isError ? paneQuery.error.message : "";
  const panePending = paneQuery !== null && paneQuery.data === undefined && !paneQuery.isError;
  const visibleError = actionError;

  return {
    lifecycleDrafts,
    policyDrafts,
    operationBoundary: boundary,
    queryClient,
    deliveryFilter,
    setDeliveryFilter: (value: BillingDeliveryFilter) => {
      if (!boundary.isLocked()) setDeliveryFilter(value);
    },
    disputeFilter,
    setDisputeFilter: (value: BillingDisputeFilter) => {
      if (!boundary.isLocked()) setDisputeFilter(value);
    },
    riskFilter,
    setRiskFilter: (value: CommercialRiskFilter) => {
      if (!boundary.isLocked()) setRiskFilter(value);
    },
    riskCursor,
    setRiskCursor,
    riskCursorHistory,
    setRiskCursorHistory,
    tab,
    setTab: (value: CommercialTab) => {
      if (!boundary.isLocked()) setTab(value);
    },
    setActionError,
    clientAction: governanceReadDenied(clientsQuery.error) ? null : clientAction,
    setClientAction,
    riskAction: governanceReadDenied(riskQuery.error) ? null : riskAction,
    setRiskAction,
    mappingAction: governanceReadDenied(billingQuery.error) ? null : mappingAction,
    setMappingAction,
    replayAction: governanceReadDenied(billingQuery.error) ? null : replayAction,
    setReplayAction,
    createDisputeAction: governanceReadDenied(billingQuery.error) ? null : createDisputeAction,
    setCreateDisputeAction,
    disputeCaseAction: governanceReadDenied(disputesQuery.error) ? null : disputeCaseAction,
    setDisputeCaseAction,
    externalReference,
    setExternalReference,
    reason,
    setReason,
    disputeCategory,
    setDisputeCategory,
    disputedUnits,
    setDisputedUnits,
    disputeSubject,
    setDisputeSubject,
    assignee,
    setAssignee,
    adjustmentKey,
    setAdjustmentKey,
    commercialQuery,
    paneQuery,
    paneError,
    panePending,
    lifecycleQuery,
    riskQuery,
    overview,
    clients,
    exports,
    risks,
    billingAccounts,
    billingDeliveries,
    billingDisputes,
    retentionPolicies,
    legalHolds,
    lifecycleEvents,
    purgeCandidates,
    sourcePurgeCandidates,
    deletedSourceAssets,
    busy,
    metrics,
    createBillingDispute,
    transitionBillingDispute,
    updateCustomerMapping,
    replayDelivery,
    updateClient,
    actOnExport,
    reviewRisk,
    saveRetentionPolicy,
    placeLegalHold,
    releaseLegalHold,
    purgeExport,
    purgeSourceAsset,
    reauthorizeSourceAsset,
    visibleError,
  };
}
