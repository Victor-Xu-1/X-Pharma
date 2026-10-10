import { DatabaseBackup, Gavel, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { StatusBadge } from "../../components/common";
import { FormStatus } from "../../components/FormStatus";
import type {
  DataExportJob,
  DataLifecycleEvent,
  DataRetentionPolicy,
  DeletedSourceAsset,
  LegalHold,
  LegalHoldScope,
  SourceAssetImpact,
} from "../../lib/contracts/commercial";
import { useLocale } from "../../lib/i18n";
import { commercialLifecycleText as t } from "../../lib/i18n/commercialLifecycle";
import { useModalFocus } from "../../lib/useModalFocus";
import { LifecycleEventRecords } from "./lifecycle/LifecycleEventRecords";
import { LifecycleHoldRecords } from "./lifecycle/LifecycleHoldRecords";
import { LifecyclePurgeRecords } from "./lifecycle/LifecyclePurgeRecords";
import { LifecycleSourceRecords } from "./lifecycle/LifecycleSourceRecords";
import type { LifecycleAction } from "./lifecycle/types";

export function DataLifecyclePanel({
  policies,
  holds,
  events,
  candidates,
  sourceCandidates,
  deletedSourceAssets,
  busy,
  error,
  onActionStart,
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
  error: string;
  onActionStart: () => void;
  onSavePolicy: (input: {
    dataClass: DataRetentionPolicy["data_class"];
    retentionSeconds: number;
    legalBasis: string;
    geographicScope: string[];
    active: boolean;
  }) => Promise<boolean>;
  onPlaceHold: (input: {
    scopeType: LegalHoldScope;
    scopeId: string | null;
    matterReference: string;
    reason: string;
  }) => Promise<boolean>;
  onReleaseHold: (hold: LegalHold, reason: string) => Promise<boolean>;
  onPurge: (job: DataExportJob, reason: string) => Promise<boolean>;
  onPurgeSource: (asset: SourceAssetImpact, reason: string) => Promise<boolean>;
  onReauthorizeSource: (asset: DeletedSourceAsset, reason: string) => Promise<boolean>;
}) {
  useLocale();
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
  const [pendingAction, setPendingAction] = useState<LifecycleAction | null>(null);
  const [actionReason, setActionReason] = useState("");
  const closeAction = () => {
    if (!busy) setPendingAction(null);
  };
  const dialogRef = useModalFocus<HTMLElement>(Boolean(pendingAction), closeAction, { closeOnEscape: !busy });

  function beginAction(action: NonNullable<typeof pendingAction>) {
    onActionStart();
    setPendingAction(action);
    setActionReason("");
  }

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
    if (busy) return;
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
    if (busy) return;
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

  async function submitHold(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (
      matterReference.trim().length < 3 ||
      holdReason.trim().length < 3 ||
      (scopeType !== "tenant" && !scopeId.trim())
    )
      return;
    const succeeded = await onPlaceHold({
      scopeType,
      scopeId: scopeType === "tenant" ? null : scopeId.trim(),
      matterReference: matterReference.trim(),
      reason: holdReason.trim(),
    });
    if (!succeeded) return;
    setMatterReference("");
    setHoldReason("");
  }

  async function confirmAction(event: FormEvent) {
    event.preventDefault();
    if (busy || !pendingAction || actionReason.trim().length < 3) return;
    const succeeded =
      pendingAction.kind === "release"
        ? await onReleaseHold(pendingAction.hold, actionReason.trim())
        : pendingAction.kind === "purge"
          ? await onPurge(pendingAction.job, actionReason.trim())
          : pendingAction.kind === "source-purge"
            ? await onPurgeSource(pendingAction.asset, actionReason.trim())
            : await onReauthorizeSource(pendingAction.asset, actionReason.trim());
    if (!succeeded) return;
    setPendingAction(null);
    setActionReason("");
  }

  return (
    <section className="lifecycle-workbench" aria-label={t("数据生命周期治理")}>
      {!pendingAction ? <FormStatus pending={Boolean(busy)} error={error} /> : null}
      <div className="lifecycle-config-grid">
        <form className="operations-form" onSubmit={submitPolicy}>
          <header>
            <div>
              <p className="eyebrow">RETENTION POLICY</p>
              <h2>{t("导出对象保留策略")}</h2>
            </div>
            <StatusBadge value={currentPolicy?.active ? "active" : "not_configured"} />
          </header>
          <label>
            {t("保留时长（小时）")}
            <input
              aria-label={t("保留时长（小时）")}
              disabled={Boolean(busy)}
              type="number"
              min="0.0834"
              step="0.25"
              value={retentionHours}
              onChange={(event) => setRetentionHours(event.target.value)}
            />
          </label>
          <label>
            {t("法律与合同依据")}
            <input
              aria-label={t("法律与合同依据")}
              disabled={Boolean(busy)}
              value={legalBasis}
              onChange={(event) => setLegalBasis(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            {t("地域范围")}
            <input
              aria-label={t("地域范围")}
              disabled={Boolean(busy)}
              value={geography}
              onChange={(event) => setGeography(event.target.value)}
              placeholder="CN, SG"
            />
          </label>
          <label className="check-control">
            <input
              type="checkbox"
              disabled={Boolean(busy)}
              checked={policyActive}
              onChange={(event) => setPolicyActive(event.target.checked)}
            />
            {t("启用策略")}
          </label>
          <button className="primary-button" type="submit" disabled={Boolean(busy) || legalBasis.trim().length < 3}>
            <DatabaseBackup size={16} />
            {t("保存策略")}
          </button>
          {currentPolicy ? (
            <p className="form-footnote">{t("当前版本 v{version}", { version: currentPolicy.policy_version })}</p>
          ) : null}
        </form>

        <form className="operations-form" onSubmit={submitSourcePolicy}>
          <header>
            <div>
              <p className="eyebrow">SOURCE RETENTION</p>
              <h2>{t("源资料保留策略")}</h2>
            </div>
            <StatusBadge value={sourcePolicy?.active ? "active" : "not_configured"} />
          </header>
          <label>
            {t("缺失后保留时长（小时）")}
            <input
              aria-label={t("源资料保留时长（小时）")}
              disabled={Boolean(busy)}
              type="number"
              min="0.0834"
              step="1"
              value={sourceRetentionHours}
              onChange={(event) => setSourceRetentionHours(event.target.value)}
            />
          </label>
          <label>
            {t("法律与合同依据")}
            <input
              aria-label={t("源资料法律与合同依据")}
              disabled={Boolean(busy)}
              value={sourceLegalBasis}
              onChange={(event) => setSourceLegalBasis(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            {t("地域范围")}
            <input
              aria-label={t("源资料地域范围")}
              disabled={Boolean(busy)}
              value={sourceGeography}
              onChange={(event) => setSourceGeography(event.target.value)}
              placeholder="CN, SG"
            />
          </label>
          <label className="check-control">
            <input
              type="checkbox"
              disabled={Boolean(busy)}
              checked={sourcePolicyActive}
              onChange={(event) => setSourcePolicyActive(event.target.checked)}
            />
            {t("启用策略")}
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={Boolean(busy) || sourceLegalBasis.trim().length < 3}
          >
            <DatabaseBackup size={16} />
            {t("保存策略")}
          </button>
          {sourcePolicy ? (
            <p className="form-footnote">{t("当前版本 v{version}", { version: sourcePolicy.policy_version })}</p>
          ) : null}
        </form>

        <form className="operations-form" onSubmit={submitHold}>
          <header>
            <div>
              <p className="eyebrow">LEGAL HOLD</p>
              <h2>{t("创建法律保全")}</h2>
            </div>
            <Gavel size={18} />
          </header>
          <label>
            {t("保全范围")}
            <select
              aria-label={t("保全范围")}
              disabled={Boolean(busy)}
              value={scopeType}
              onChange={(event) => setScopeType(event.target.value as LegalHoldScope)}
            >
              <option value="tenant">{t("整个租户")}</option>
              <option value="billing_account">{t("计费账户")}</option>
              <option value="data_export_job">{t("导出任务")}</option>
              <option value="data_source">{t("资料源")}</option>
              <option value="source_asset">{t("源资料资产")}</option>
            </select>
          </label>
          {scopeType !== "tenant" ? (
            <label>
              {t("范围 ID")}
              <input
                aria-label={t("保全范围 ID")}
                disabled={Boolean(busy)}
                value={scopeId}
                onChange={(event) => setScopeId(event.target.value)}
              />
            </label>
          ) : null}
          <label>
            {t("事项编号")}
            <input
              aria-label={t("事项编号")}
              disabled={Boolean(busy)}
              value={matterReference}
              onChange={(event) => setMatterReference(event.target.value)}
              maxLength={200}
            />
          </label>
          <label>
            {t("保全原因")}
            <textarea
              aria-label={t("保全原因")}
              disabled={Boolean(busy)}
              value={holdReason}
              onChange={(event) => setHoldReason(event.target.value)}
              maxLength={2000}
            />
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={
              Boolean(busy) ||
              matterReference.trim().length < 3 ||
              holdReason.trim().length < 3 ||
              (scopeType !== "tenant" && !scopeId.trim())
            }
          >
            <Gavel size={16} />
            {t("启动保全")}
          </button>
        </form>
      </div>

      <LifecycleHoldRecords holds={holds} busy={busy} beginAction={beginAction} />

      <LifecycleSourceRecords
        sourceCandidates={sourceCandidates}
        deletedSourceAssets={deletedSourceAssets}
        busy={busy}
        beginAction={beginAction}
      />

      <LifecyclePurgeRecords candidates={candidates} busy={busy} beginAction={beginAction} />

      <LifecycleEventRecords events={events} />

      {pendingAction ? (
        <div className="modal-backdrop" role="presentation">
          <section
            ref={dialogRef}
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="lifecycle-action-title"
            tabIndex={-1}
          >
            <header>
              <div>
                <p className="eyebrow">CONTROLLED ACTION</p>
                <h2 id="lifecycle-action-title">
                  {pendingAction.kind === "release"
                    ? t("解除法律保全")
                    : pendingAction.kind === "source-purge"
                      ? t("撤回源资料")
                      : pendingAction.kind === "source-reauthorize"
                        ? t("重新授权源资料")
                        : t("清除到期导出对象")}
                </h2>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={closeAction}
                aria-label={t("关闭")}
                disabled={Boolean(busy)}
              >
                <X size={18} />
              </button>
            </header>
            <form onSubmit={confirmAction}>
              <label>
                {t("操作原因")}
                <textarea
                  aria-label={t("生命周期操作原因")}
                  value={actionReason}
                  onChange={(event) => setActionReason(event.target.value)}
                  maxLength={2000}
                  disabled={Boolean(busy)}
                />
              </label>
              <FormStatus pending={Boolean(busy)} error={error} />
              <div className="form-actions">
                <button className="text-button" type="button" onClick={closeAction} disabled={Boolean(busy)}>
                  {t("取消")}
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={Boolean(busy) || actionReason.trim().length < 3}
                >
                  {t("确认执行")}
                </button>
              </div>
            </form>
          </section>
        </div>
      ) : null}
    </section>
  );
}
