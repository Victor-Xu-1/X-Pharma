import { CircleDollarSign, DatabaseBackup, ReceiptText, RefreshCw, Scale, ShieldAlert, Users } from "lucide-react";
import { ErrorState, formatDate, Spinner } from "../components/common";
import { commercialKeys } from "../lib/contracts/commercial";
import { BillingDisputeTable } from "./commercial/BillingDisputeTable";
import { BillingDisputeTransitionModal } from "./commercial/BillingDisputeTransitionModal";
import { BillingOperations } from "./commercial/BillingOperations";
import { BillingReplayModal } from "./commercial/BillingReplayModal";
import { ClientStatusModal } from "./commercial/ClientStatusModal";
import { ClientTable } from "./commercial/ClientTable";
import { CreateBillingDisputeModal } from "./commercial/CreateBillingDisputeModal";
import { CustomerMappingModal } from "./commercial/CustomerMappingModal";
import { DataLifecyclePanel } from "./commercial/DataLifecyclePanel";
import { ExportTable } from "./commercial/ExportTable";
import { units } from "./commercial/format";
import { Metric } from "./commercial/Metric";
import { RiskPanel } from "./commercial/RiskPanel";
import { RiskReviewModal } from "./commercial/RiskReviewModal";
import { SubscriptionTable } from "./commercial/SubscriptionTable";
import { useCommercialWorkspace } from "./commercial/useCommercialWorkspace";
import { WorkspaceExportPolicyPanel } from "./WorkspaceExportPolicyPanel";

export function CommercialView() {
  const {
    queryClient,
    deliveryFilter,
    setDeliveryFilter,
    disputeFilter,
    setDisputeFilter,
    riskFilter,
    setRiskFilter,
    riskCursor,
    setRiskCursor,
    riskCursorHistory,
    setRiskCursorHistory,
    tab,
    setTab,
    setActionError,
    clientAction,
    setClientAction,
    riskAction,
    setRiskAction,
    mappingAction,
    setMappingAction,
    replayAction,
    setReplayAction,
    createDisputeAction,
    setCreateDisputeAction,
    disputeCaseAction,
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
  } = useCommercialWorkspace();

  return (
    <section className="commercial-workbench">
      <div className="commercial-toolbar">
        <span>{overview ? `统计截止 ${formatDate(overview.as_of, true)}` : "商业概况尚未读取"}</span>
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            setActionError("");
            void queryClient.invalidateQueries({ queryKey: commercialKeys.root, refetchType: "active" });
          }}
          disabled={Boolean(busy) || Boolean(paneQuery?.isFetching)}
        >
          <RefreshCw size={16} />
          刷新
        </button>
      </div>
      {visibleError ? (
        <p className="inline-error" role="alert">
          {visibleError}
        </p>
      ) : null}
      {commercialQuery.isError && tab !== "overview" ? (
        <ErrorState message={commercialQuery.error.message} retry={commercialQuery.refetch} />
      ) : null}
      {overview && !commercialQuery.isError ? (
        <section className="commercial-metrics" aria-label="商业运营指标">
          <Metric icon={<CircleDollarSign size={18} />} label="可用额度" value={units(metrics.available)} />
          <Metric icon={<CircleDollarSign size={18} />} label="累计消耗" value={units(metrics.consumed)} />
          <Metric icon={<Users size={18} />} label="活跃客户端" value={String(metrics.activeClients)} />
          <Metric
            icon={<ReceiptText size={18} />}
            label="账单死信"
            value={String(metrics.deadDeliveries)}
            danger={metrics.deadDeliveries > 0}
          />
          <Metric
            icon={<ShieldAlert size={18} />}
            label="未处置风险"
            value={String(metrics.openRisks)}
            danger={metrics.openRisks > 0}
          />
          <Metric
            icon={<Scale size={18} />}
            label="处理中争议"
            value={String(metrics.openDisputes)}
            danger={metrics.openDisputes > 0}
          />
          <Metric icon={<DatabaseBackup size={18} />} label="执行中导出" value={String(metrics.pendingExports)} />
        </section>
      ) : null}
      <div className="tab-bar" role="tablist" aria-label="商业运营视图">
        {(
          ["overview", "clients", "billing", "disputes", "exports", "export-policy", "risks", "lifecycle"] as const
        ).map((key) => (
          <button
            key={key}
            className={tab === key ? "active" : ""}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
          >
            {
              {
                overview: "合同与额度",
                clients: "Agent 客户端",
                billing: "账单投递",
                disputes: "计费争议",
                exports: "数据导出",
                "export-policy": "导出策略",
                risks: "风险事件",
                lifecycle: "数据生命周期",
              }[key]
            }
          </button>
        ))}
      </div>
      {paneError ? (
        <ErrorState
          message={paneError}
          retry={() => {
            void paneQuery?.refetch();
          }}
        />
      ) : panePending ? (
        <Spinner label="正在读取商业运营数据" />
      ) : (
        <>
          {tab === "overview" && overview ? <SubscriptionTable items={overview.subscriptions} /> : null}
          {tab === "clients" ? (
            <ClientTable
              items={clients}
              busy={busy}
              onAction={(action) => {
                setClientAction(action);
                setReason("");
              }}
            />
          ) : null}
          {tab === "billing" ? (
            <BillingOperations
              accounts={billingAccounts}
              deliveries={billingDeliveries}
              deliveryFilter={deliveryFilter}
              busy={busy}
              onDeliveryFilter={setDeliveryFilter}
              onMapping={(account) => {
                setMappingAction({ account });
                setExternalReference("");
                setReason("");
              }}
              onReplay={(delivery) => {
                setReplayAction({ delivery });
                setReason("");
              }}
              onDispute={(delivery) => {
                setCreateDisputeAction({
                  delivery,
                  disputeKey: `dispute.${Date.now()}.${delivery.statement_id.slice(0, 8)}`,
                });
                setDisputeCategory("usage");
                setDisputedUnits("");
                setDisputeSubject("");
                setReason("");
              }}
            />
          ) : null}
          {tab === "disputes" ? (
            <BillingDisputeTable
              items={billingDisputes}
              filter={disputeFilter}
              busy={busy}
              onFilter={setDisputeFilter}
              onAction={(dispute) => {
                setDisputeCaseAction({
                  dispute,
                  action: dispute.status === "open" ? "investigate" : "resolve_no_credit",
                  operationKey: `dispute.operation.${Date.now()}.${dispute.id.slice(0, 8)}`,
                });
                setReason("");
                setAssignee(dispute.assigned_to ?? "");
                setDisputedUnits("");
                setAdjustmentKey(`dispute.credit.${Date.now()}.${dispute.id.slice(0, 8)}`);
              }}
            />
          ) : null}
          {tab === "exports" ? (
            <ExportTable items={exports} busy={busy} onAction={(job, action) => void actOnExport(job, action)} />
          ) : null}
          {tab === "export-policy" ? <WorkspaceExportPolicyPanel /> : null}
          {tab === "risks" ? (
            <RiskPanel
              items={risks}
              totalItems={riskQuery.data?.total_items ?? 0}
              nextCursor={riskQuery.data?.next_cursor ?? null}
              filter={riskFilter}
              isPending={riskQuery.isPending}
              canGoPrevious={riskCursorHistory.length > 0}
              busy={busy}
              onFilter={(value) => {
                setRiskFilter(value);
                setRiskCursor(null);
                setRiskCursorHistory([]);
              }}
              onPrevious={() => {
                const previousIndex = riskCursorHistory.length - 1;
                if (previousIndex < 0) return;
                setRiskCursor(riskCursorHistory[previousIndex] ?? null);
                setRiskCursorHistory(riskCursorHistory.slice(0, previousIndex));
              }}
              onNext={(nextCursor) => {
                setRiskCursorHistory([...riskCursorHistory, riskCursor]);
                setRiskCursor(nextCursor);
              }}
              onAction={(action) => {
                setRiskAction(action);
                setReason(action.event.case_notes);
              }}
            />
          ) : null}
          {tab === "lifecycle" && lifecycleQuery.data ? (
            <DataLifecyclePanel
              policies={retentionPolicies}
              holds={legalHolds}
              events={lifecycleEvents}
              candidates={purgeCandidates}
              sourceCandidates={sourcePurgeCandidates}
              deletedSourceAssets={deletedSourceAssets}
              busy={busy}
              onSavePolicy={(input) => void saveRetentionPolicy(input)}
              onPlaceHold={(input) => void placeLegalHold(input)}
              onReleaseHold={(hold, releaseReason) => void releaseLegalHold(hold, releaseReason)}
              onPurge={(job, purgeReason) => void purgeExport(job, purgeReason)}
              onPurgeSource={(asset, purgeReason) => void purgeSourceAsset(asset, purgeReason)}
              onReauthorizeSource={(asset, actionReason) => void reauthorizeSourceAsset(asset, actionReason)}
            />
          ) : null}
        </>
      )}
      {clientAction ? (
        <ClientStatusModal
          action={clientAction}
          reason={reason}
          busy={Boolean(busy)}
          onReason={setReason}
          onClose={() => setClientAction(null)}
          onSubmit={updateClient}
        />
      ) : null}
      {riskAction ? (
        <RiskReviewModal
          action={riskAction}
          reason={reason}
          busy={Boolean(busy)}
          onReason={setReason}
          onStatus={(status) => setRiskAction({ ...riskAction, status })}
          onClose={() => setRiskAction(null)}
          onSubmit={reviewRisk}
        />
      ) : null}
      {mappingAction ? (
        <CustomerMappingModal
          action={mappingAction}
          externalReference={externalReference}
          reason={reason}
          busy={Boolean(busy)}
          onExternalReference={setExternalReference}
          onReason={setReason}
          onClose={() => setMappingAction(null)}
          onSubmit={updateCustomerMapping}
        />
      ) : null}
      {replayAction ? (
        <BillingReplayModal
          action={replayAction}
          reason={reason}
          busy={Boolean(busy)}
          onReason={setReason}
          onClose={() => setReplayAction(null)}
          onSubmit={replayDelivery}
        />
      ) : null}
      {createDisputeAction ? (
        <CreateBillingDisputeModal
          action={createDisputeAction}
          category={disputeCategory}
          units={disputedUnits}
          subject={disputeSubject}
          description={reason}
          busy={Boolean(busy)}
          onCategory={setDisputeCategory}
          onUnits={setDisputedUnits}
          onSubject={setDisputeSubject}
          onDescription={setReason}
          onClose={() => setCreateDisputeAction(null)}
          onSubmit={createBillingDispute}
        />
      ) : null}
      {disputeCaseAction ? (
        <BillingDisputeTransitionModal
          action={disputeCaseAction}
          notes={reason}
          assignee={assignee}
          units={disputedUnits}
          adjustmentKey={adjustmentKey}
          busy={Boolean(busy)}
          onAction={(action) => setDisputeCaseAction({ ...disputeCaseAction, action })}
          onNotes={setReason}
          onAssignee={setAssignee}
          onUnits={setDisputedUnits}
          onAdjustmentKey={setAdjustmentKey}
          onClose={() => setDisputeCaseAction(null)}
          onSubmit={transitionBillingDispute}
        />
      ) : null}
    </section>
  );
}
