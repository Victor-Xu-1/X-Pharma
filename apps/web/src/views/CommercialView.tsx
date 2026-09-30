import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Ban,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  DatabaseBackup,
  Gavel,
  Link2,
  Power,
  ReceiptText,
  RefreshCw,
  RotateCcw,
  Scale,
  ShieldAlert,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";

import { EmptyState, ErrorState, formatDate, humanBytes, Spinner, StatusBadge } from "../components/common";
import {
  type BillingAccount,
  type BillingDelivery,
  type BillingDeliveryFilter,
  type BillingDispute,
  type BillingDisputeAction,
  type BillingDisputeCategory,
  type BillingDisputeFilter,
  type CommercialClient,
  type CommercialOperation,
  type CommercialOverview,
  type CommercialRiskEvent,
  type CommercialRiskFilter,
  commercialKeys,
  type DataExportJob,
  type DataLifecycleEvent,
  type DataRetentionPolicy,
  type DeletedSourceAsset,
  executeCommercialOperation,
  type LegalHold,
  type LegalHoldScope,
  loadCommercialRiskPage,
  loadCommercialWorkspace,
  loadLifecycleWorkspace,
  type RiskCaseStatus,
  type SourceAssetImpact,
} from "../lib/contracts/commercial";
import { WorkspaceExportPolicyPanel } from "./WorkspaceExportPolicyPanel";

type CommercialTab =
  | "overview"
  | "clients"
  | "billing"
  | "disputes"
  | "exports"
  | "export-policy"
  | "risks"
  | "lifecycle";
type ClientAction = { client: CommercialClient; active: boolean };
type RiskAction = { event: CommercialRiskEvent; status: Exclude<RiskCaseStatus, "open"> };
type MappingAction = { account: BillingAccount };
type ReplayAction = { delivery: BillingDelivery };
type CreateDisputeAction = { delivery: BillingDelivery; disputeKey: string };
type DisputeCaseAction = { dispute: BillingDispute; action: BillingDisputeAction; operationKey: string };

function units(value: number): string {
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
}

function sumUnits(values: string[]): number {
  return values.reduce((sum, value) => sum + (Number(value) || 0), 0);
}

export function CommercialView() {
  const queryClient = useQueryClient();
  const [deliveryFilter, setDeliveryFilter] = useState<BillingDeliveryFilter>("all");
  const [disputeFilter, setDisputeFilter] = useState<BillingDisputeFilter>("all");
  const [riskFilter, setRiskFilter] = useState<CommercialRiskFilter>("all");
  const [riskCursor, setRiskCursor] = useState<string | null>(null);
  const [riskCursorHistory, setRiskCursorHistory] = useState<Array<string | null>>([]);
  const [tab, setTab] = useState<CommercialTab>("overview");
  const [actionError, setActionError] = useState("");
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
    queryKey: commercialKeys.workspace(deliveryFilter, disputeFilter),
    queryFn: ({ signal }) => loadCommercialWorkspace(deliveryFilter, disputeFilter, signal),
    placeholderData: (previous) => previous,
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
  const operationMutation = useMutation({
    mutationFn: ({ operation }: { busyKey: string; operation: CommercialOperation }) =>
      executeCommercialOperation(operation),
  });
  const workspace = commercialQuery.data;
  const overview = workspace?.overview ?? null;
  const clients = workspace?.clients ?? [];
  const exports = workspace?.exports ?? [];
  const risks = riskQuery.data?.items ?? [];
  const billingAccounts = workspace?.billingAccounts ?? [];
  const billingDeliveries = workspace?.billingDeliveries ?? [];
  const billingDisputes = workspace?.billingDisputes ?? [];
  const retentionPolicies = lifecycleQuery.data?.retentionPolicies ?? [];
  const legalHolds = lifecycleQuery.data?.legalHolds ?? [];
  const lifecycleEvents = lifecycleQuery.data?.lifecycleEvents ?? [];
  const purgeCandidates = lifecycleQuery.data?.purgeCandidates ?? [];
  const sourcePurgeCandidates = lifecycleQuery.data?.sourcePurgeCandidates ?? [];
  const deletedSourceAssets = lifecycleQuery.data?.deletedSourceAssets ?? [];
  const busy = operationMutation.isPending ? (operationMutation.variables?.busyKey ?? "operation") : "";

  async function runOperation(busyKey: string, operation: CommercialOperation, fallback: string): Promise<boolean> {
    setActionError("");
    try {
      await operationMutation.mutateAsync({ busyKey, operation });
      await queryClient.invalidateQueries({ queryKey: commercialKeys.root, refetchType: "active" });
      return true;
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : fallback);
      return false;
    }
  }

  const metrics = useMemo(
    () => ({
      available: sumUnits(overview?.subscriptions.map((item) => item.available_units) ?? []),
      consumed: sumUnits(overview?.subscriptions.map((item) => item.consumed_units) ?? []),
      activeClients: clients.filter((item) => item.active).length,
      openRisks: overview?.open_risk_count ?? 0,
      pendingExports: exports.filter((item) => ["pending_approval", "queued", "running"].includes(item.state)).length,
      deadDeliveries: billingDeliveries.filter((item) => item.state === "dead").length,
      openDisputes: billingDisputes.filter((item) => ["open", "investigating"].includes(item.status)).length,
    }),
    [billingDeliveries, billingDisputes, clients, exports, overview],
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
    await runOperation(
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
    await runOperation(
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
    await runOperation(
      `lifecycle:hold:${hold.id}`,
      { kind: "release-legal-hold", holdId: hold.id, requestBody: { reason } },
      "Legal hold 解除失败",
    );
  }

  async function purgeExport(job: DataExportJob, reason: string) {
    await runOperation(
      `lifecycle:purge:${job.id}`,
      {
        kind: "purge-export",
        jobId: job.id,
        requestBody: { idempotency_key: `web.purge.${crypto.randomUUID()}`, reason },
      },
      "导出对象清除失败",
    );
  }

  async function purgeSourceAsset(asset: SourceAssetImpact, reason: string) {
    await runOperation(
      `lifecycle:source-purge:${asset.id}`,
      {
        kind: "purge-source",
        assetId: asset.id,
        requestBody: { idempotency_key: `web.source-purge.${crypto.randomUUID()}`, reason },
      },
      "源资料清除失败",
    );
  }

  async function reauthorizeSourceAsset(asset: DeletedSourceAsset, reason: string) {
    await runOperation(
      `lifecycle:source-reauthorize:${asset.id}`,
      {
        kind: "reauthorize-source",
        assetId: asset.id,
        requestBody: { idempotency_key: `web.source-reauthorize.${crypto.randomUUID()}`, reason },
      },
      "源资料重新授权失败",
    );
  }

  const queryError = commercialQuery.error ?? lifecycleQuery.error ?? riskQuery.error;
  const visibleError =
    actionError || (queryError instanceof Error ? queryError.message : queryError ? "商业运营数据加载失败" : "");

  if (!overview && commercialQuery.isPending) return <Spinner label="正在读取商业运营数据" />;
  if (!overview) return <ErrorState message={visibleError || "商业运营数据加载失败"} retry={commercialQuery.refetch} />;

  return (
    <section className="commercial-workbench">
      <div className="commercial-toolbar">
        <span>统计截止 {formatDate(overview.as_of, true)}</span>
        <button
          className="secondary-button"
          type="button"
          onClick={() => {
            setActionError("");
            void queryClient.invalidateQueries({ queryKey: commercialKeys.root, refetchType: "active" });
          }}
          disabled={Boolean(busy) || commercialQuery.isFetching}
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
          danger={billingDisputes.some((item) => item.overdue)}
        />
        <Metric icon={<DatabaseBackup size={18} />} label="执行中导出" value={String(metrics.pendingExports)} />
      </section>
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
      {tab === "overview" ? <SubscriptionTable items={overview.subscriptions} /> : null}
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
      {tab === "lifecycle" && lifecycleQuery.isPending ? <Spinner label="正在读取数据生命周期策略" /> : null}
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

function Metric({
  icon,
  label,
  value,
  danger = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  danger?: boolean;
}) {
  return (
    <div className={danger ? "danger" : ""}>
      {icon}
      <span>
        <strong>{value}</strong>
        <small>{label}</small>
      </span>
    </div>
  );
}

function SubscriptionTable({ items }: { items: CommercialOverview["subscriptions"] }) {
  if (!items.length) return <EmptyState title="暂无商业订阅" />;
  return (
    <div className="table-frame commercial-table">
      <table>
        <thead>
          <tr>
            <th>客户 / 订阅</th>
            <th>计费账户</th>
            <th>状态</th>
            <th>授予额度</th>
            <th>已消耗</th>
            <th>已预留</th>
            <th>可用额度</th>
            <th>今日记录</th>
            <th>权益</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.subscription_id}>
              <td>
                <strong>{item.client_name}</strong>
                <span className="cell-subtitle mono-cell">{item.subscription_key}</span>
              </td>
              <td>
                {item.billing_account_name}
                <span className="cell-subtitle mono-cell">{item.billing_account_key}</span>
              </td>
              <td>
                <StatusBadge value={item.status} />
              </td>
              <td>{item.granted_units}</td>
              <td>{item.consumed_units}</td>
              <td>{item.reserved_units}</td>
              <td>
                <strong>{item.available_units}</strong>
              </td>
              <td>{item.daily_unique_records}</td>
              <td>{item.entitlements.length}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ClientTable({
  items,
  busy,
  onAction,
}: {
  items: CommercialClient[];
  busy: string;
  onAction: (action: ClientAction) => void;
}) {
  return (
    <div className="table-frame commercial-table">
      <table>
        <thead>
          <tr>
            <th>客户端</th>
            <th>订阅</th>
            <th>计费账户</th>
            <th>状态</th>
            <th>主体</th>
            <th>可用额度</th>
            <th>活跃预留</th>
            <th>24h 拒绝</th>
            <th>最近策略事件</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {!items.length && (
            <tr>
              <td colSpan={10}>
                <EmptyState title="暂无 Agent 客户端" />
              </td>
            </tr>
          )}
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.display_name}</strong>
                <span className="cell-subtitle mono-cell">{item.client_key}</span>
              </td>
              <td className="mono-cell">{item.subscription_key ?? "--"}</td>
              <td className="mono-cell">{item.billing_account_key ?? "--"}</td>
              <td>
                <StatusBadge value={item.active ? "active" : "revoked"} />
              </td>
              <td>{item.subjects.filter((subject) => subject.active).length}</td>
              <td>{item.available_units ?? "--"}</td>
              <td>{item.active_reservations}</td>
              <td className={item.denial_count_24h ? "danger-text" : ""}>{item.denial_count_24h}</td>
              <td>{formatDate(item.last_policy_event_at, true)}</td>
              <td>
                <button
                  className={item.active ? "icon-button danger-text" : "icon-button"}
                  type="button"
                  disabled={busy === `client:${item.id}`}
                  title={item.active ? "停用客户端" : "重新启用"}
                  aria-label={`${item.active ? "停用" : "启用"} ${item.display_name}`}
                  onClick={() => onAction({ client: item, active: !item.active })}
                >
                  {item.active ? <Ban size={17} /> : <Power size={17} />}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function BillingOperations({
  accounts,
  deliveries,
  deliveryFilter,
  busy,
  onDeliveryFilter,
  onMapping,
  onReplay,
  onDispute,
}: {
  accounts: BillingAccount[];
  deliveries: BillingDelivery[];
  deliveryFilter: BillingDeliveryFilter;
  busy: string;
  onDeliveryFilter: (value: BillingDeliveryFilter) => void;
  onMapping: (account: BillingAccount) => void;
  onReplay: (delivery: BillingDelivery) => void;
  onDispute: (delivery: BillingDelivery) => void;
}) {
  return (
    <div className="billing-operations">
      <section aria-labelledby="billing-accounts-title">
        <div className="billing-section-heading">
          <h2 id="billing-accounts-title">计费账户映射</h2>
        </div>
        <div className="table-frame commercial-table">
          <table>
            <thead>
              <tr>
                <th>计费账户</th>
                <th>币种</th>
                <th>状态</th>
                <th>Provider 客户编号</th>
                <th>账期单</th>
                <th>待开票</th>
                <th>发票</th>
                <th>更新时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {!accounts.length ? (
                <tr>
                  <td colSpan={9}>
                    <EmptyState title="暂无计费账户" />
                  </td>
                </tr>
              ) : null}
              {accounts.map((account) => (
                <tr key={account.id}>
                  <td>
                    <strong>{account.display_name}</strong>
                    <span className="cell-subtitle mono-cell">{account.account_key}</span>
                  </td>
                  <td>{account.currency}</td>
                  <td>
                    <StatusBadge value={account.status} />
                  </td>
                  <td className="mono-cell">{account.external_customer_reference_masked ?? "未配置"}</td>
                  <td>{account.statement_count}</td>
                  <td className={account.unresolved_statement_count ? "danger-text" : ""}>
                    {account.unresolved_statement_count}
                  </td>
                  <td>{account.invoice_count}</td>
                  <td>{formatDate(account.updated_at, true)}</td>
                  <td>
                    <button
                      className="icon-button"
                      type="button"
                      disabled={busy === `mapping:${account.id}`}
                      title="配置 Provider 客户编号"
                      aria-label={`配置 ${account.display_name} 的 Provider 客户编号`}
                      onClick={() => onMapping(account)}
                    >
                      <Link2 size={17} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section aria-labelledby="billing-deliveries-title">
        <div className="billing-section-heading">
          <h2 id="billing-deliveries-title">Provider 投递队列</h2>
          <label>
            <span>投递状态</span>
            <select
              aria-label="投递状态"
              value={deliveryFilter}
              onChange={(event) => onDeliveryFilter(event.target.value as BillingDeliveryFilter)}
            >
              <option value="all">全部</option>
              <option value="pending">待处理</option>
              <option value="processing">处理中</option>
              <option value="retry">待重试</option>
              <option value="succeeded">已成功</option>
              <option value="dead">死信</option>
            </select>
          </label>
        </div>
        <div className="table-frame commercial-table">
          <table>
            <thead>
              <tr>
                <th>账期单</th>
                <th>计费账户</th>
                <th>状态</th>
                <th>尝试次数</th>
                <th>Provider 发票</th>
                <th>可执行时间</th>
                <th>完成时间</th>
                <th>最近错误</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {!deliveries.length ? (
                <tr>
                  <td colSpan={9}>
                    <EmptyState title="暂无账单投递记录" />
                  </td>
                </tr>
              ) : null}
              {deliveries.map((delivery) => (
                <tr key={delivery.event_id}>
                  <td>
                    <strong>{delivery.statement_key}</strong>
                    <span className="cell-subtitle mono-cell">{delivery.statement_id}</span>
                  </td>
                  <td>
                    {delivery.billing_account_name}
                    <span className="cell-subtitle mono-cell">{delivery.billing_account_key}</span>
                  </td>
                  <td>
                    <StatusBadge value={delivery.state} />
                  </td>
                  <td>{delivery.attempts}</td>
                  <td className="mono-cell">{delivery.external_invoice_id ?? "--"}</td>
                  <td>{formatDate(delivery.available_at, true)}</td>
                  <td>{formatDate(delivery.processed_at, true)}</td>
                  <td>
                    <span className="billing-error" title={delivery.last_error ?? undefined}>
                      {delivery.last_error ?? "--"}
                    </span>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="icon-button"
                        type="button"
                        title="发起计费争议"
                        aria-label={`对账期单 ${delivery.statement_key} 发起计费争议`}
                        onClick={() => onDispute(delivery)}
                      >
                        <Scale size={17} />
                      </button>
                      {delivery.state === "dead" && delivery.delivery_id ? (
                        <button
                          className="icon-button"
                          type="button"
                          disabled={busy === `replay:${delivery.delivery_id}`}
                          title="重放死信"
                          aria-label={`重放账期单 ${delivery.statement_key}`}
                          onClick={() => onReplay(delivery)}
                        >
                          <RotateCcw size={17} />
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function BillingDisputeTable({
  items,
  filter,
  busy,
  onFilter,
  onAction,
}: {
  items: BillingDispute[];
  filter: BillingDisputeFilter;
  busy: string;
  onFilter: (value: BillingDisputeFilter) => void;
  onAction: (dispute: BillingDispute) => void;
}) {
  return (
    <div className="billing-operations">
      <div className="billing-section-heading">
        <h2>计费争议案件</h2>
        <label>
          <span>案件状态</span>
          <select
            aria-label="争议状态"
            value={filter}
            onChange={(event) => onFilter(event.target.value as BillingDisputeFilter)}
          >
            <option value="all">全部</option>
            <option value="open">待受理</option>
            <option value="investigating">调查中</option>
            <option value="resolved">已解决</option>
            <option value="rejected">已驳回</option>
            <option value="cancelled">已取消</option>
          </select>
        </label>
      </div>
      <div className="table-frame commercial-table">
        <table>
          <thead>
            <tr>
              <th>案件 / 主题</th>
              <th>计费账户</th>
              <th>账期单</th>
              <th>争议额度</th>
              <th>类别</th>
              <th>状态</th>
              <th>负责人</th>
              <th>SLA</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {!items.length ? (
              <tr>
                <td colSpan={9}>
                  <EmptyState title="暂无计费争议" />
                </td>
              </tr>
            ) : null}
            {items.map((item) => (
              <tr key={item.id}>
                <td>
                  <strong>{item.subject}</strong>
                  <span className="cell-subtitle mono-cell">{item.dispute_key}</span>
                </td>
                <td>
                  {item.billing_account_name}
                  <span className="cell-subtitle mono-cell">{item.billing_account_key}</span>
                </td>
                <td className="mono-cell">{item.statement_key}</td>
                <td>{item.disputed_units}</td>
                <td>{item.category}</td>
                <td>
                  <StatusBadge value={item.status} />
                </td>
                <td>{item.assigned_to ?? "未分配"}</td>
                <td className={item.overdue ? "danger-text" : ""}>{formatDate(item.due_at, true)}</td>
                <td>
                  {["resolved", "rejected", "cancelled"].includes(item.status) ? (
                    "--"
                  ) : (
                    <button
                      className="icon-button"
                      type="button"
                      disabled={busy === `dispute:${item.id}`}
                      title="处理计费争议"
                      aria-label={`处理计费争议 ${item.dispute_key}`}
                      onClick={() => onAction(item)}
                    >
                      <Scale size={17} />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function CreateBillingDisputeModal({
  action,
  category,
  units,
  subject,
  description,
  busy,
  onCategory,
  onUnits,
  onSubject,
  onDescription,
  onClose,
  onSubmit,
}: {
  action: CreateDisputeAction;
  category: BillingDisputeCategory;
  units: string;
  subject: string;
  description: string;
  busy: boolean;
  onCategory: (value: BillingDisputeCategory) => void;
  onUnits: (value: string) => void;
  onSubject: (value: string) => void;
  onDescription: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const valid = Number(units) > 0 && subject.trim().length >= 3 && description.trim().length >= 3;
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="create-dispute-title">
        <header>
          <div>
            <p className="eyebrow">BILLING DISPUTE</p>
            <h2 id="create-dispute-title">发起计费争议</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.delivery.statement_key}
            <span className="mono-cell">{action.delivery.billing_account_name}</span>
          </p>
          <label>
            <span>争议类别</span>
            <select value={category} onChange={(event) => onCategory(event.target.value as BillingDisputeCategory)}>
              <option value="usage">用量</option>
              <option value="pricing">定价</option>
              <option value="duplicate">重复计费</option>
              <option value="authorization">授权</option>
              <option value="service">服务</option>
              <option value="other">其他</option>
            </select>
          </label>
          <label>
            <span>争议额度</span>
            <input
              aria-label="争议额度"
              type="number"
              min="0.00000001"
              step="0.00000001"
              required
              value={units}
              onChange={(event) => onUnits(event.target.value)}
            />
          </label>
          <label>
            <span>主题</span>
            <input
              aria-label="争议主题"
              minLength={3}
              maxLength={200}
              required
              value={subject}
              onChange={(event) => onSubject(event.target.value)}
            />
          </label>
          <label>
            <span>争议说明</span>
            <textarea
              aria-label="争议说明"
              rows={4}
              minLength={3}
              maxLength={4000}
              required
              value={description}
              onChange={(event) => onDescription(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || !valid}>
              提交争议
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function BillingDisputeTransitionModal({
  action,
  notes,
  assignee,
  units,
  adjustmentKey,
  busy,
  onAction,
  onNotes,
  onAssignee,
  onUnits,
  onAdjustmentKey,
  onClose,
  onSubmit,
}: {
  action: DisputeCaseAction;
  notes: string;
  assignee: string;
  units: string;
  adjustmentKey: string;
  busy: boolean;
  onAction: (value: BillingDisputeAction) => void;
  onNotes: (value: string) => void;
  onAssignee: (value: string) => void;
  onUnits: (value: string) => void;
  onAdjustmentKey: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  const credit = action.action === "resolve_credit";
  const valid = notes.trim().length >= 3 && (!credit || (Number(units) > 0 && adjustmentKey.trim().length >= 8));
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="transition-dispute-title">
        <header>
          <div>
            <p className="eyebrow">BILLING DISPUTE</p>
            <h2 id="transition-dispute-title">处理计费争议</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.dispute.subject}
            <span>{action.dispute.description}</span>
            <span className="mono-cell">
              争议额度 {action.dispute.disputed_units} · 版本 {action.dispute.version}
            </span>
          </p>
          <label>
            <span>处理动作</span>
            <select
              aria-label="争议处理动作"
              value={action.action}
              onChange={(event) => onAction(event.target.value as BillingDisputeAction)}
            >
              {action.dispute.status === "open" ? <option value="investigate">受理并调查</option> : null}
              {action.dispute.status === "investigating" ? <option value="resolve_no_credit">确认无退款</option> : null}
              {action.dispute.status === "investigating" ? <option value="resolve_credit">退款额度</option> : null}
              {action.dispute.status === "investigating" ? <option value="reject">驳回</option> : null}
              <option value="cancel">取消案件</option>
            </select>
          </label>
          <label>
            <span>负责人</span>
            <input maxLength={500} value={assignee} onChange={(event) => onAssignee(event.target.value)} />
          </label>
          {credit ? (
            <>
              <label>
                <span>退款额度</span>
                <input
                  aria-label="退款额度"
                  type="number"
                  min="0.00000001"
                  max={action.dispute.disputed_units}
                  step="0.00000001"
                  required
                  value={units}
                  onChange={(event) => onUnits(event.target.value)}
                />
              </label>
              <label>
                <span>账本调整键</span>
                <input
                  aria-label="账本调整键"
                  minLength={8}
                  maxLength={199}
                  required
                  value={adjustmentKey}
                  onChange={(event) => onAdjustmentKey(event.target.value)}
                />
              </label>
            </>
          ) : null}
          <label>
            <span>处理记录</span>
            <textarea
              aria-label="争议处理记录"
              rows={4}
              minLength={3}
              maxLength={4000}
              required
              value={notes}
              onChange={(event) => onNotes(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || !valid}>
              提交处理
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function DataLifecyclePanel({
  policies,
  holds,
  events,
  candidates,
  sourceCandidates,
  deletedSourceAssets,
  busy,
  onSavePolicy,
  onPlaceHold,
  onReleaseHold,
  onPurge,
  onPurgeSource,
  onReauthorizeSource,
}: {
  policies: DataRetentionPolicy[];
  holds: LegalHold[];
  events: DataLifecycleEvent[];
  candidates: DataExportJob[];
  sourceCandidates: SourceAssetImpact[];
  deletedSourceAssets: DeletedSourceAsset[];
  busy: string;
  onSavePolicy: (input: {
    dataClass: DataRetentionPolicy["data_class"];
    retentionSeconds: number;
    legalBasis: string;
    geographicScope: string[];
    active: boolean;
  }) => void;
  onPlaceHold: (input: {
    scopeType: LegalHoldScope;
    scopeId: string | null;
    matterReference: string;
    reason: string;
  }) => void;
  onReleaseHold: (hold: LegalHold, reason: string) => void;
  onPurge: (job: DataExportJob, reason: string) => void;
  onPurgeSource: (asset: SourceAssetImpact, reason: string) => void;
  onReauthorizeSource: (asset: DeletedSourceAsset, reason: string) => void;
}) {
  const currentPolicy = policies.find((policy) => policy.data_class === "commercial_export_artifact");
  const sourcePolicy = policies.find((policy) => policy.data_class === "source_asset_snapshot");
  const [retentionHours, setRetentionHours] = useState("24");
  const [legalBasis, setLegalBasis] = useState("");
  const [geography, setGeography] = useState("CN");
  const [policyActive, setPolicyActive] = useState(true);
  const [sourceRetentionHours, setSourceRetentionHours] = useState("720");
  const [sourceLegalBasis, setSourceLegalBasis] = useState("");
  const [sourceGeography, setSourceGeography] = useState("CN");
  const [sourcePolicyActive, setSourcePolicyActive] = useState(true);
  const [scopeType, setScopeType] = useState<LegalHoldScope>("tenant");
  const [scopeId, setScopeId] = useState("");
  const [matterReference, setMatterReference] = useState("");
  const [holdReason, setHoldReason] = useState("");
  const [pendingAction, setPendingAction] = useState<
    | { kind: "release"; hold: LegalHold }
    | { kind: "purge"; job: DataExportJob }
    | { kind: "source-purge"; asset: SourceAssetImpact }
    | { kind: "source-reauthorize"; asset: DeletedSourceAsset }
    | null
  >(null);
  const [actionReason, setActionReason] = useState("");

  useEffect(() => {
    if (!currentPolicy) return;
    setRetentionHours(String(currentPolicy.retention_seconds / 3600));
    setLegalBasis(currentPolicy.legal_basis);
    setGeography(currentPolicy.geographic_scope.join(", "));
    setPolicyActive(currentPolicy.active);
  }, [currentPolicy]);

  useEffect(() => {
    if (!sourcePolicy) return;
    setSourceRetentionHours(String(sourcePolicy.retention_seconds / 3600));
    setSourceLegalBasis(sourcePolicy.legal_basis);
    setSourceGeography(sourcePolicy.geographic_scope.join(", "));
    setSourcePolicyActive(sourcePolicy.active);
  }, [sourcePolicy]);

  function submitPolicy(event: FormEvent) {
    event.preventDefault();
    const hours = Number(retentionHours);
    if (!Number.isFinite(hours) || hours < 5 / 60 || legalBasis.trim().length < 3) return;
    onSavePolicy({
      dataClass: "commercial_export_artifact",
      retentionSeconds: Math.round(hours * 3600),
      legalBasis: legalBasis.trim(),
      geographicScope: geography
        .split(",")
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
      active: policyActive,
    });
  }

  function submitSourcePolicy(event: FormEvent) {
    event.preventDefault();
    const hours = Number(sourceRetentionHours);
    if (!Number.isFinite(hours) || hours < 5 / 60 || sourceLegalBasis.trim().length < 3) return;
    onSavePolicy({
      dataClass: "source_asset_snapshot",
      retentionSeconds: Math.round(hours * 3600),
      legalBasis: sourceLegalBasis.trim(),
      geographicScope: sourceGeography
        .split(",")
        .map((item) => item.trim().toUpperCase())
        .filter(Boolean),
      active: sourcePolicyActive,
    });
  }

  function submitHold(event: FormEvent) {
    event.preventDefault();
    if (
      matterReference.trim().length < 3 ||
      holdReason.trim().length < 3 ||
      (scopeType !== "tenant" && !scopeId.trim())
    )
      return;
    onPlaceHold({
      scopeType,
      scopeId: scopeType === "tenant" ? null : scopeId.trim(),
      matterReference: matterReference.trim(),
      reason: holdReason.trim(),
    });
    setMatterReference("");
    setHoldReason("");
  }

  function confirmAction(event: FormEvent) {
    event.preventDefault();
    if (!pendingAction || actionReason.trim().length < 3) return;
    if (pendingAction.kind === "release") onReleaseHold(pendingAction.hold, actionReason.trim());
    else if (pendingAction.kind === "purge") onPurge(pendingAction.job, actionReason.trim());
    else if (pendingAction.kind === "source-purge") onPurgeSource(pendingAction.asset, actionReason.trim());
    else onReauthorizeSource(pendingAction.asset, actionReason.trim());
    setPendingAction(null);
    setActionReason("");
  }

  return (
    <section className="lifecycle-workbench" aria-label="数据生命周期治理">
      <div className="lifecycle-config-grid">
        <form className="operations-form" onSubmit={submitPolicy}>
          <header>
            <div>
              <p className="eyebrow">RETENTION POLICY</p>
              <h2>导出对象保留策略</h2>
            </div>
            <StatusBadge value={currentPolicy?.active ? "active" : "not_configured"} />
          </header>
          <label>
            保留时长（小时）
            <input
              aria-label="保留时长（小时）"
              type="number"
              min="0.0834"
              step="0.25"
              value={retentionHours}
              onChange={(event) => setRetentionHours(event.target.value)}
            />
          </label>
          <label>
            法律与合同依据
            <input
              aria-label="法律与合同依据"
              value={legalBasis}
              onChange={(event) => setLegalBasis(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            地域范围
            <input
              aria-label="地域范围"
              value={geography}
              onChange={(event) => setGeography(event.target.value)}
              placeholder="CN, SG"
            />
          </label>
          <label className="check-control">
            <input type="checkbox" checked={policyActive} onChange={(event) => setPolicyActive(event.target.checked)} />
            启用策略
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={busy === "lifecycle:policy:commercial_export_artifact" || legalBasis.trim().length < 3}
          >
            <DatabaseBackup size={16} />
            保存策略
          </button>
          {currentPolicy ? <p className="form-footnote">当前版本 v{currentPolicy.policy_version}</p> : null}
        </form>

        <form className="operations-form" onSubmit={submitSourcePolicy}>
          <header>
            <div>
              <p className="eyebrow">SOURCE RETENTION</p>
              <h2>源资料保留策略</h2>
            </div>
            <StatusBadge value={sourcePolicy?.active ? "active" : "not_configured"} />
          </header>
          <label>
            缺失后保留时长（小时）
            <input
              aria-label="源资料保留时长（小时）"
              type="number"
              min="0.0834"
              step="1"
              value={sourceRetentionHours}
              onChange={(event) => setSourceRetentionHours(event.target.value)}
            />
          </label>
          <label>
            法律与合同依据
            <input
              aria-label="源资料法律与合同依据"
              value={sourceLegalBasis}
              onChange={(event) => setSourceLegalBasis(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            地域范围
            <input
              aria-label="源资料地域范围"
              value={sourceGeography}
              onChange={(event) => setSourceGeography(event.target.value)}
              placeholder="CN, SG"
            />
          </label>
          <label className="check-control">
            <input
              type="checkbox"
              checked={sourcePolicyActive}
              onChange={(event) => setSourcePolicyActive(event.target.checked)}
            />
            启用策略
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={busy === "lifecycle:policy:source_asset_snapshot" || sourceLegalBasis.trim().length < 3}
          >
            <DatabaseBackup size={16} />
            保存策略
          </button>
          {sourcePolicy ? <p className="form-footnote">当前版本 v{sourcePolicy.policy_version}</p> : null}
        </form>

        <form className="operations-form" onSubmit={submitHold}>
          <header>
            <div>
              <p className="eyebrow">LEGAL HOLD</p>
              <h2>创建法律保全</h2>
            </div>
            <Gavel size={18} />
          </header>
          <label>
            保全范围
            <select
              aria-label="保全范围"
              value={scopeType}
              onChange={(event) => setScopeType(event.target.value as LegalHoldScope)}
            >
              <option value="tenant">整个租户</option>
              <option value="billing_account">计费账户</option>
              <option value="data_export_job">导出任务</option>
              <option value="data_source">资料源</option>
              <option value="source_asset">源资料资产</option>
            </select>
          </label>
          {scopeType !== "tenant" ? (
            <label>
              范围 ID
              <input aria-label="保全范围 ID" value={scopeId} onChange={(event) => setScopeId(event.target.value)} />
            </label>
          ) : null}
          <label>
            事项编号
            <input
              aria-label="事项编号"
              value={matterReference}
              onChange={(event) => setMatterReference(event.target.value)}
              maxLength={200}
            />
          </label>
          <label>
            保全原因
            <textarea
              aria-label="保全原因"
              value={holdReason}
              onChange={(event) => setHoldReason(event.target.value)}
              maxLength={2000}
            />
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={
              busy === "lifecycle:hold" ||
              matterReference.trim().length < 3 ||
              holdReason.trim().length < 3 ||
              (scopeType !== "tenant" && !scopeId.trim())
            }
          >
            <Gavel size={16} />
            启动保全
          </button>
        </form>
      </div>

      <section className="operations-section">
        <header>
          <div>
            <p className="eyebrow">ACTIVE HOLDS</p>
            <h2>法律保全记录</h2>
          </div>
        </header>
        {!holds.length ? (
          <EmptyState title="暂无法律保全记录" />
        ) : (
          <div className="table-frame commercial-table">
            <table>
              <thead>
                <tr>
                  <th>事项</th>
                  <th>范围</th>
                  <th>状态</th>
                  <th>创建时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {holds.map((hold) => (
                  <tr key={hold.id}>
                    <td>
                      <strong>{hold.matter_reference}</strong>
                      <span className="cell-subtitle">{hold.reason}</span>
                    </td>
                    <td>
                      {hold.scope_type}
                      <span className="cell-subtitle mono-cell">{hold.scope_id ?? "tenant-wide"}</span>
                    </td>
                    <td>
                      <StatusBadge value={hold.status} />
                    </td>
                    <td>{formatDate(hold.placed_at, true)}</td>
                    <td>
                      {hold.status === "active" ? (
                        <button
                          className="icon-button"
                          type="button"
                          title="解除法律保全"
                          aria-label={`解除法律保全 ${hold.matter_reference}`}
                          disabled={busy === `lifecycle:hold:${hold.id}`}
                          onClick={() => {
                            setPendingAction({ kind: "release", hold });
                            setActionReason("");
                          }}
                        >
                          <Check size={17} />
                        </button>
                      ) : (
                        "--"
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="operations-section" data-lifecycle="source-withdrawal">
        <header>
          <div>
            <p className="eyebrow">SOURCE WITHDRAWAL</p>
            <h2>源资料撤回候选</h2>
          </div>
        </header>
        {!sourceCandidates.length ? (
          <EmptyState title="暂无超过保留期的缺失源资料" />
        ) : (
          <div className="table-frame commercial-table">
            <table>
              <thead>
                <tr>
                  <th>资料</th>
                  <th>缺失时间</th>
                  <th>依赖影响</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {sourceCandidates.map((asset) => (
                  <tr key={asset.id}>
                    <td>
                      <strong>{asset.file_name}</strong>
                      <span className="cell-subtitle mono-cell">{asset.logical_path}</span>
                    </td>
                    <td>{asset.missing_since ? formatDate(asset.missing_since, true) : "--"}</td>
                    <td>
                      {asset.version_count} 个版本 / {asset.staged_fact_count} 个治理事实
                      <span className="cell-subtitle">
                        {asset.blockers.length ? asset.blockers.join(", ") : "依赖闭包已验证"}
                      </span>
                    </td>
                    <td>
                      <StatusBadge value={asset.blockers.length ? "blocked" : "eligible"} />
                    </td>
                    <td>
                      <button
                        className="icon-button danger-text"
                        type="button"
                        title={asset.blockers.length ? "存在业务依赖，执行后将记录阻断事件" : "撤回源资料"}
                        aria-label={`撤回源资料 ${asset.file_name}`}
                        disabled={busy === `lifecycle:source-purge:${asset.id}`}
                        onClick={() => {
                          setPendingAction({ kind: "source-purge", asset });
                          setActionReason("");
                        }}
                      >
                        <Trash2 size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="operations-section" data-lifecycle="source-reauthorization">
        <header>
          <div>
            <p className="eyebrow">SOURCE REAUTHORIZATION</p>
            <h2>已撤回源资料</h2>
          </div>
        </header>
        {!deletedSourceAssets.length ? (
          <EmptyState title="暂无等待重新授权的源资料" />
        ) : (
          <div className="table-frame commercial-table">
            <table>
              <thead>
                <tr>
                  <th>资料</th>
                  <th>撤回时间</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {deletedSourceAssets.map((asset) => (
                  <tr key={asset.id}>
                    <td>
                      <strong>{asset.file_name}</strong>
                      <span className="cell-subtitle mono-cell">{asset.logical_path}</span>
                    </td>
                    <td>{formatDate(asset.updated_at, true)}</td>
                    <td>
                      <StatusBadge value={asset.state} />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        type="button"
                        title="重新授权并等待自动扫描"
                        aria-label={`重新授权源资料 ${asset.file_name}`}
                        disabled={busy === `lifecycle:source-reauthorize:${asset.id}`}
                        onClick={() => {
                          setPendingAction({ kind: "source-reauthorize", asset });
                          setActionReason("");
                        }}
                      >
                        <RotateCcw size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="operations-section">
        <header>
          <div>
            <p className="eyebrow">PURGE CANDIDATES</p>
            <h2>到期导出对象</h2>
          </div>
        </header>
        {!candidates.length ? (
          <EmptyState title="暂无符合策略的清除候选项" />
        ) : (
          <div className="table-frame commercial-table">
            <table>
              <thead>
                <tr>
                  <th>任务</th>
                  <th>数据集</th>
                  <th>文件大小</th>
                  <th>到期时间</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {candidates.map((job) => (
                  <tr key={job.id}>
                    <td className="mono-cell">{job.id}</td>
                    <td>{job.dataset}</td>
                    <td>{humanBytes(job.artifact_bytes)}</td>
                    <td>{job.expires_at ? formatDate(job.expires_at, true) : "--"}</td>
                    <td>
                      <button
                        className="icon-button danger-text"
                        type="button"
                        title="清除到期对象"
                        aria-label={`清除到期对象 ${job.id}`}
                        disabled={busy === `lifecycle:purge:${job.id}`}
                        onClick={() => {
                          setPendingAction({ kind: "purge", job });
                          setActionReason("");
                        }}
                      >
                        <Trash2 size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="operations-section">
        <header>
          <div>
            <p className="eyebrow">IMMUTABLE AUDIT</p>
            <h2>生命周期审计</h2>
          </div>
        </header>
        {!events.length ? (
          <EmptyState title="暂无生命周期执行事件" />
        ) : (
          <div className="table-frame commercial-table">
            <table>
              <thead>
                <tr>
                  <th>时间</th>
                  <th>目标</th>
                  <th>动作</th>
                  <th>结果</th>
                  <th>策略版本</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => (
                  <tr key={item.id}>
                    <td>{formatDate(item.created_at, true)}</td>
                    <td className="mono-cell">{item.target_id}</td>
                    <td>{item.action}</td>
                    <td>
                      <StatusBadge value={item.outcome} />
                    </td>
                    <td>v{item.policy_version}</td>
                    <td>{item.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {pendingAction ? (
        <div className="modal-backdrop" role="presentation">
          <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="lifecycle-action-title">
            <header>
              <div>
                <p className="eyebrow">CONTROLLED ACTION</p>
                <h2 id="lifecycle-action-title">
                  {pendingAction.kind === "release"
                    ? "解除法律保全"
                    : pendingAction.kind === "source-purge"
                      ? "撤回源资料"
                      : pendingAction.kind === "source-reauthorize"
                        ? "重新授权源资料"
                        : "清除到期导出对象"}
                </h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setPendingAction(null)} aria-label="关闭">
                <X size={18} />
              </button>
            </header>
            <form onSubmit={confirmAction}>
              <label>
                操作原因
                <textarea
                  aria-label="生命周期操作原因"
                  value={actionReason}
                  onChange={(event) => setActionReason(event.target.value)}
                  maxLength={2000}
                />
              </label>
              <div className="form-actions">
                <button className="text-button" type="button" onClick={() => setPendingAction(null)}>
                  取消
                </button>
                <button className="primary-button" type="submit" disabled={actionReason.trim().length < 3}>
                  确认执行
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}

function ExportTable({
  items,
  busy,
  onAction,
}: {
  items: DataExportJob[];
  busy: string;
  onAction: (job: DataExportJob, action: "approve" | "cancel") => void;
}) {
  if (!items.length) return <EmptyState title="暂无数据导出任务" />;
  return (
    <div className="table-frame commercial-table">
      <table>
        <thead>
          <tr>
            <th>数据集 / 任务</th>
            <th>格式</th>
            <th>状态</th>
            <th>申请上限</th>
            <th>实际记录</th>
            <th>文件大小</th>
            <th>申请时间</th>
            <th>审批人</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.dataset}</strong>
                <span className="cell-subtitle mono-cell">{item.id}</span>
              </td>
              <td>{item.format.toUpperCase()}</td>
              <td>
                <StatusBadge value={item.state} />
              </td>
              <td>{item.max_records}</td>
              <td>{item.record_count}</td>
              <td>{humanBytes(item.artifact_bytes)}</td>
              <td>{formatDate(item.requested_at, true)}</td>
              <td>{item.approved_by ?? "--"}</td>
              <td>
                <div className="row-actions">
                  {item.state === "pending_approval" ? (
                    <button
                      className="icon-button"
                      type="button"
                      disabled={busy === `export:${item.id}`}
                      title="批准导出"
                      aria-label={`批准导出 ${item.id}`}
                      onClick={() => onAction(item, "approve")}
                    >
                      <Check size={17} />
                    </button>
                  ) : null}
                  {["pending_approval", "queued", "running"].includes(item.state) ? (
                    <button
                      className="icon-button danger-text"
                      type="button"
                      disabled={busy === `export:${item.id}`}
                      title="取消导出"
                      aria-label={`取消导出 ${item.id}`}
                      onClick={() => onAction(item, "cancel")}
                    >
                      <X size={17} />
                    </button>
                  ) : null}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RiskPanel({
  items,
  totalItems,
  nextCursor,
  filter,
  isPending,
  canGoPrevious,
  busy,
  onFilter,
  onPrevious,
  onNext,
  onAction,
}: {
  items: CommercialRiskEvent[];
  totalItems: number;
  nextCursor: string | null;
  filter: CommercialRiskFilter;
  isPending: boolean;
  canGoPrevious: boolean;
  busy: string;
  onFilter: (value: CommercialRiskFilter) => void;
  onPrevious: () => void;
  onNext: (cursor: string) => void;
  onAction: (action: RiskAction) => void;
}) {
  return (
    <section className="risk-operations" aria-label="风险事件队列">
      <div className="risk-queue-toolbar">
        <label>
          <span>处置状态</span>
          <select
            aria-label="风险处置状态"
            value={filter}
            onChange={(event) => onFilter(event.target.value as CommercialRiskFilter)}
          >
            <option value="all">全部</option>
            <option value="open">未处置</option>
            <option value="acknowledged">已确认</option>
            <option value="resolved">已解决</option>
            <option value="dismissed">已排除</option>
          </select>
        </label>
        <span className="risk-queue-count" aria-live="polite">
          {isPending ? "正在读取" : `共 ${totalItems} 条`}
        </span>
        <div className="risk-queue-pagination">
          <button
            className="icon-button"
            type="button"
            title="上一页"
            aria-label="风险事件上一页"
            disabled={isPending || !canGoPrevious}
            onClick={onPrevious}
          >
            <ChevronLeft size={17} />
          </button>
          <button
            className="icon-button"
            type="button"
            title="下一页"
            aria-label="风险事件下一页"
            disabled={isPending || !nextCursor}
            onClick={() => {
              if (nextCursor) onNext(nextCursor);
            }}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
      {isPending ? <Spinner label="正在读取风险事件" /> : <RiskTable items={items} busy={busy} onAction={onAction} />}
    </section>
  );
}

function RiskTable({
  items,
  busy,
  onAction,
}: {
  items: CommercialRiskEvent[];
  busy: string;
  onAction: (action: RiskAction) => void;
}) {
  if (!items.length) return <EmptyState title="暂无商业风险事件" />;
  return (
    <div className="table-frame commercial-table">
      <table>
        <thead>
          <tr>
            <th>客户端 / 主体</th>
            <th>拒绝原因</th>
            <th>权益 / 阶段</th>
            <th>深度</th>
            <th>申请记录</th>
            <th>累计唯一记录</th>
            <th>发生时间</th>
            <th>处置状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.client_name}</strong>
                <span className="cell-subtitle mono-cell">{item.subject_id}</span>
              </td>
              <td>
                <span className="risk-reason">{item.reason_code}</span>
              </td>
              <td>
                {item.entitlement_key}
                <span className="cell-subtitle">{item.phase}</span>
              </td>
              <td>{item.page_depth}</td>
              <td>{item.requested_records}</td>
              <td>{item.projected_unique_records}</td>
              <td>{formatDate(item.occurred_at, true)}</td>
              <td>
                <StatusBadge value={item.case_status} />
              </td>
              <td>
                {item.case_status === "resolved" || item.case_status === "dismissed" ? (
                  "--"
                ) : (
                  <button
                    className="icon-button"
                    type="button"
                    disabled={busy === `risk:${item.id}`}
                    title="处置风险事件"
                    aria-label={`处置风险事件 ${item.client_name}`}
                    onClick={() =>
                      onAction({ event: item, status: item.case_status === "open" ? "acknowledged" : "resolved" })
                    }
                  >
                    <ShieldAlert size={17} />
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CustomerMappingModal({
  action,
  externalReference,
  reason,
  busy,
  onExternalReference,
  onReason,
  onClose,
  onSubmit,
}: {
  action: MappingAction;
  externalReference: string;
  reason: string;
  busy: boolean;
  onExternalReference: (value: string) => void;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="customer-mapping-title">
        <header>
          <div>
            <p className="eyebrow">BILLING PROVIDER</p>
            <h2 id="customer-mapping-title">配置客户编号</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.account.display_name}
            <span className="mono-cell">{action.account.account_key}</span>
          </p>
          <label>
            <span>Provider 客户编号</span>
            <input
              required
              minLength={1}
              maxLength={500}
              pattern="[A-Za-z0-9][A-Za-z0-9._:/-]{0,499}"
              autoComplete="off"
              value={externalReference}
              onChange={(event) => onExternalReference(event.target.value)}
            />
          </label>
          <label>
            <span>变更原因</span>
            <textarea
              rows={4}
              required
              minLength={3}
              maxLength={500}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={busy || externalReference.trim().length < 1 || reason.trim().length < 3}
            >
              保存映射
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function BillingReplayModal({
  action,
  reason,
  busy,
  onReason,
  onClose,
  onSubmit,
}: {
  action: ReplayAction;
  reason: string;
  busy: boolean;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="billing-replay-title">
        <header>
          <div>
            <p className="eyebrow">DEAD LETTER</p>
            <h2 id="billing-replay-title">重放账单投递</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.delivery.statement_key}
            <span>{action.delivery.last_error ?? "--"}</span>
          </p>
          <label>
            <span>重放原因</span>
            <textarea
              rows={4}
              required
              minLength={3}
              maxLength={500}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy || reason.trim().length < 3}>
              确认重放
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function ClientStatusModal({
  action,
  reason,
  busy,
  onReason,
  onClose,
  onSubmit,
}: {
  action: ClientAction;
  reason: string;
  busy: boolean;
  onReason: (value: string) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="client-status-title">
        <header>
          <div>
            <p className="eyebrow">AGENT CLIENT</p>
            <h2 id="client-status-title">{action.active ? "重新启用客户端" : "停用客户端"}</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.client.display_name}
            <span className="mono-cell">{action.client.client_key}</span>
          </p>
          <label>
            <span>操作原因</span>
            <textarea
              rows={4}
              required
              minLength={3}
              maxLength={500}
              value={reason}
              onChange={(event) => onReason(event.target.value)}
            />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button
              className={action.active ? "primary-button" : "danger-button"}
              type="submit"
              disabled={busy || reason.trim().length < 3}
            >
              {action.active ? "确认启用" : "确认停用"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function RiskReviewModal({
  action,
  reason,
  busy,
  onReason,
  onStatus,
  onClose,
  onSubmit,
}: {
  action: RiskAction;
  reason: string;
  busy: boolean;
  onReason: (value: string) => void;
  onStatus: (status: RiskAction["status"]) => void;
  onClose: () => void;
  onSubmit: (event: FormEvent) => void;
}) {
  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="risk-review-title">
        <header>
          <div>
            <p className="eyebrow">POLICY RISK</p>
            <h2 id="risk-review-title">处置风险事件</h2>
          </div>
          <button className="icon-button" type="button" onClick={onClose} aria-label="关闭">
            <X size={18} />
          </button>
        </header>
        <form onSubmit={onSubmit}>
          <p className="commercial-modal-subject">
            {action.event.client_name}
            <span>{action.event.reason_code}</span>
          </p>
          <label>
            <span>处置状态</span>
            <select value={action.status} onChange={(event) => onStatus(event.target.value as RiskAction["status"])}>
              <option value="acknowledged">已确认</option>
              <option value="resolved">已解决</option>
              <option value="dismissed">不构成风险</option>
            </select>
          </label>
          <label>
            <span>处置记录</span>
            <textarea rows={4} maxLength={2000} value={reason} onChange={(event) => onReason(event.target.value)} />
          </label>
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit" disabled={busy}>
              提交处置
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
