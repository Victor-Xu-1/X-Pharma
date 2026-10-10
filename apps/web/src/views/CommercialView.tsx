import { CircleDollarSign, DatabaseBackup, ReceiptText, RefreshCw, Scale, ShieldAlert, Users } from "lucide-react";
import { ErrorState, formatDate, Spinner } from "../components/common";
import { ResearchTabList } from "../components/ResearchTabList";
import { commercialKeys } from "../lib/contracts/commercial";
import { useLocale } from "../lib/i18n";
import { commercialWorkspaceText as t } from "../lib/i18n/commercialWorkspace";
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
import { reportedCount, units } from "./commercial/format";
import { Metric } from "./commercial/Metric";
import { RiskPanel } from "./commercial/RiskPanel";
import { RiskReviewModal } from "./commercial/RiskReviewModal";
import { SubscriptionTable } from "./commercial/SubscriptionTable";
import { useCommercialWorkspace } from "./commercial/useCommercialWorkspace";
import { WorkspaceExportPolicyPanel } from "./WorkspaceExportPolicyPanel";

export function CommercialView() {
  useLocale();
  const {
    lifecycleDrafts,
    policyDrafts,
    operationBoundary,
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
        <span>
          {overview ? t("统计截止 {time}", { time: formatDate(overview.as_of, true) }) : t("商业概况尚未读取")}
        </span>
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
          {t("刷新")}
        </button>
      </div>
      {visibleError &&
      tab !== "lifecycle" &&
      tab !== "export-policy" &&
      !(clientAction || riskAction || mappingAction || replayAction || createDisputeAction || disputeCaseAction) ? (
        <p className="inline-error" role="alert">
          {visibleError}
        </p>
      ) : null}
      {commercialQuery.isError && tab !== "overview" ? (
        <ErrorState message={commercialQuery.error.message} retry={commercialQuery.refetch} />
      ) : null}
      {tab === "overview" && overview && !commercialQuery.isError ? (
        <section className="commercial-metrics" aria-label={t("商业运营指标")}>
          <Metric icon={<CircleDollarSign size={18} />} label={t("可用额度")} value={units(metrics.available)} />
          <Metric icon={<CircleDollarSign size={18} />} label={t("累计消耗")} value={units(metrics.consumed)} />
          <Metric icon={<Users size={18} />} label={t("活跃客户端")} value={reportedCount(metrics.activeClients)} />
          <Metric
            icon={<ReceiptText size={18} />}
            label={t("账单死信")}
            value={reportedCount(metrics.deadDeliveries)}
            danger={(metrics.deadDeliveries ?? 0) > 0}
          />
          <Metric
            icon={<ShieldAlert size={18} />}
            label={t("未处置风险")}
            value={reportedCount(metrics.openRisks)}
            danger={(metrics.openRisks ?? 0) > 0}
          />
          <Metric
            icon={<Scale size={18} />}
            label={t("处理中争议")}
            value={reportedCount(metrics.openDisputes)}
            danger={(metrics.openDisputes ?? 0) > 0}
          />
          <Metric
            icon={<DatabaseBackup size={18} />}
            label={t("执行中导出")}
            value={reportedCount(metrics.pendingExports)}
          />
        </section>
      ) : null}
      <ResearchTabList
        idPrefix="commercial"
        ariaLabel={t("商业运营视图")}
        activeTab={tab}
        onChange={setTab}
        tabs={[
          {
            key: "overview",
            label: t("合同与额度"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "clients",
            label: t("Agent 客户端"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "billing",
            label: t("账单投递"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "disputes",
            label: t("计费争议"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "exports",
            label: t("数据导出"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "export-policy",
            label: t("导出策略"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "risks",
            label: t("风险事件"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
          {
            key: "lifecycle",
            label: t("数据生命周期"),
            panelId: "commercial-active-panel",
            disabled: Boolean(busy),
            disabledReason: t("正在提交操作，请稍候。"),
          },
        ]}
      />
      <div role="tabpanel" id="commercial-active-panel" aria-labelledby={`commercial-tab-${tab}`}>
        {paneError ? (
          <ErrorState
            message={paneError}
            retry={() => {
              void paneQuery?.refetch();
            }}
          />
        ) : panePending ? (
          <Spinner label={t("正在读取商业运营数据")} />
        ) : (
          <>
            {tab === "overview" && overview ? <SubscriptionTable items={overview.subscriptions} /> : null}
            {tab === "clients" ? (
              <ClientTable
                items={clients}
                busy={busy}
                onAction={(action) => {
                  setActionError("");
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
                  setActionError("");
                  setMappingAction({ account });
                  setExternalReference("");
                  setReason("");
                }}
                onReplay={(delivery) => {
                  setActionError("");
                  setReplayAction({ delivery });
                  setReason("");
                }}
                onDispute={(delivery) => {
                  setActionError("");
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
                  setActionError("");
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
            {tab === "export-policy" ? (
              <WorkspaceExportPolicyPanel boundary={operationBoundary} draftState={policyDrafts} />
            ) : null}
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
                  setActionError("");
                  setRiskAction(action);
                  setReason(action.event.case_notes);
                }}
              />
            ) : null}
            {tab === "lifecycle" && lifecycleQuery.data ? (
              <DataLifecyclePanel
                drafts={lifecycleDrafts}
                refreshing={lifecycleQuery.isFetching}
                holds={legalHolds}
                events={lifecycleEvents}
                candidates={purgeCandidates}
                sourceCandidates={sourcePurgeCandidates}
                deletedSourceAssets={deletedSourceAssets}
                busy={busy}
                error={visibleError}
                onActionStart={() => setActionError("")}
                onSavePolicy={saveRetentionPolicy}
                onPlaceHold={placeLegalHold}
                onReleaseHold={releaseLegalHold}
                onPurge={purgeExport}
                onPurgeSource={purgeSourceAsset}
                onReauthorizeSource={reauthorizeSourceAsset}
              />
            ) : null}
          </>
        )}
      </div>
      {clientAction ? (
        <ClientStatusModal
          error={visibleError}
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
          error={visibleError}
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
          error={visibleError}
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
          error={visibleError}
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
          error={visibleError}
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
          error={visibleError}
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
