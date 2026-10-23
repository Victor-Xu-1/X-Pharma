import { useIsFetching, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { collectionsKeys } from "../../lib/contracts/collections";
import {
  type BillingDeliveryFilter,
  type BillingDisputeFilter,
  type CommercialOperation,
  type CommercialRiskFilter,
  commercialKeys,
  type DataExportJob,
  loadCommercialBilling,
  loadCommercialClients,
  loadCommercialDisputes,
  loadCommercialExports,
  loadCommercialOverview,
  loadCommercialRiskPage,
  loadLifecycleWorkspace,
} from "../../lib/contracts/commercial";
import { type commercialWorkspaceMessages, commercialWorkspaceText as t } from "../../lib/i18n/commercialWorkspace";
import { governanceReadDenied } from "../governance/governanceQueryState";
import { commercialFormOperations } from "./commercialFormOperations";
import { sumUnits } from "./format";
import { lifecycleOperations } from "./lifecycle/lifecycleOperations";
import { useLifecycleDrafts } from "./lifecycle/useLifecycleDrafts";
import { useWorkspacePolicyDrafts } from "./policy/useWorkspacePolicy";
import type { CommercialTab } from "./types";
import { useCommercialActionDrafts } from "./useCommercialActionDrafts";
import { useCommercialOperationBoundary } from "./useCommercialOperationBoundary";

export function useCommercialWorkspace() {
  const queryClient = useQueryClient();
  const policyFetching = useIsFetching({ queryKey: collectionsKeys.policy, exact: true }) > 0;

  const [deliveryFilter, setDeliveryFilter] = useState<BillingDeliveryFilter>("all");

  const [disputeFilter, setDisputeFilter] = useState<BillingDisputeFilter>("all");

  const [riskFilter, setRiskFilter] = useState<CommercialRiskFilter>("all");

  const [riskCursor, setRiskCursor] = useState<string | null>(null);

  const [riskCursorHistory, setRiskCursorHistory] = useState<Array<string | null>>([]);

  const [tab, setTab] = useState<CommercialTab>("overview");

  const boundary = useCommercialOperationBoundary();
  const policyDrafts = useWorkspacePolicyDrafts();
  const { busy, actionError, setActionError } = boundary;

  const actionDrafts = useCommercialActionDrafts();

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

  async function actOnExport(job: DataExportJob, action: "approve" | "cancel") {
    const actionKey = `export:${job.id}`;
    await runOperation(actionKey, { kind: "act-on-export", jobId: job.id, action }, "导出任务操作失败");
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
    refreshing:
      commercialQuery.isFetching || Boolean(paneQuery?.isFetching) || (tab === "export-policy" && policyFetching),
    refresh: async () => {
      if (boundary.isLocked()) return;
      setActionError("");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: commercialKeys.root, refetchType: "active" }),
        ...(tab === "export-policy"
          ? [queryClient.invalidateQueries({ queryKey: collectionsKeys.policy, exact: true, refetchType: "active" })]
          : []),
      ]);
    },
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
    ...actionDrafts,
    clientAction: governanceReadDenied(clientsQuery.error) ? null : actionDrafts.clientAction,
    riskAction: governanceReadDenied(riskQuery.error) ? null : actionDrafts.riskAction,
    mappingAction: governanceReadDenied(billingQuery.error) ? null : actionDrafts.mappingAction,
    replayAction: governanceReadDenied(billingQuery.error) ? null : actionDrafts.replayAction,
    createDisputeAction: governanceReadDenied(billingQuery.error) ? null : actionDrafts.createDisputeAction,
    disputeCaseAction: governanceReadDenied(disputesQuery.error) ? null : actionDrafts.disputeCaseAction,
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
    ...commercialFormOperations(runOperation, actionDrafts),
    ...lifecycleOperations(runOperation),
    actOnExport,
    visibleError,
  };
}
