import { Check, DatabaseBackup, Gavel, RotateCcw, Trash2, X } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { EmptyState, formatDate, humanBytes, StatusBadge } from "../../components/common";
import { FormStatus } from "../../components/FormStatus";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type {
  DataExportJob,
  DataLifecycleEvent,
  DataRetentionPolicy,
  DeletedSourceAsset,
  LegalHold,
  LegalHoldScope,
  SourceAssetImpact,
} from "../../lib/contracts/commercial";
import { useModalFocus } from "../../lib/useModalFocus";

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
    <section className="lifecycle-workbench" aria-label="数据生命周期治理">
      {!pendingAction ? <FormStatus pending={Boolean(busy)} error={error} /> : null}
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
              disabled={Boolean(busy)}
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
              disabled={Boolean(busy)}
              value={legalBasis}
              onChange={(event) => setLegalBasis(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            地域范围
            <input
              aria-label="地域范围"
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
            启用策略
          </label>
          <button className="primary-button" type="submit" disabled={Boolean(busy) || legalBasis.trim().length < 3}>
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
              disabled={Boolean(busy)}
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
              disabled={Boolean(busy)}
              value={sourceLegalBasis}
              onChange={(event) => setSourceLegalBasis(event.target.value)}
              maxLength={500}
            />
          </label>
          <label>
            地域范围
            <input
              aria-label="源资料地域范围"
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
            启用策略
          </label>
          <button
            className="primary-button"
            type="submit"
            disabled={Boolean(busy) || sourceLegalBasis.trim().length < 3}
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
              disabled={Boolean(busy)}
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
              <input
                aria-label="保全范围 ID"
                disabled={Boolean(busy)}
                value={scopeId}
                onChange={(event) => setScopeId(event.target.value)}
              />
            </label>
          ) : null}
          <label>
            事项编号
            <input
              aria-label="事项编号"
              disabled={Boolean(busy)}
              value={matterReference}
              onChange={(event) => setMatterReference(event.target.value)}
              maxLength={200}
            />
          </label>
          <label>
            保全原因
            <textarea
              aria-label="保全原因"
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
          <ScrollableTableRegion className="commercial-table" ariaLabel="法律保全记录滚动区域">
            <table aria-label="法律保全记录">
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
                          disabled={Boolean(busy)}
                          onClick={() => beginAction({ kind: "release", hold })}
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
          </ScrollableTableRegion>
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
          <ScrollableTableRegion className="commercial-table" ariaLabel="源资料撤回候选滚动区域">
            <table aria-label="源资料撤回候选">
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
                        disabled={Boolean(busy)}
                        onClick={() => beginAction({ kind: "source-purge", asset })}
                      >
                        <Trash2 size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
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
          <ScrollableTableRegion className="commercial-table" ariaLabel="已撤回源资料滚动区域">
            <table aria-label="已撤回源资料">
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
                        disabled={Boolean(busy)}
                        onClick={() => beginAction({ kind: "source-reauthorize", asset })}
                      >
                        <RotateCcw size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
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
          <ScrollableTableRegion className="commercial-table" ariaLabel="到期导出对象滚动区域">
            <table aria-label="到期导出对象">
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
                        disabled={Boolean(busy)}
                        onClick={() => beginAction({ kind: "purge", job })}
                      >
                        <Trash2 size={17} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
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
          <ScrollableTableRegion className="commercial-table" ariaLabel="生命周期审计滚动区域">
            <table aria-label="生命周期审计">
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
          </ScrollableTableRegion>
        )}
      </section>

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
                    ? "解除法律保全"
                    : pendingAction.kind === "source-purge"
                      ? "撤回源资料"
                      : pendingAction.kind === "source-reauthorize"
                        ? "重新授权源资料"
                        : "清除到期导出对象"}
                </h2>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={closeAction}
                aria-label="关闭"
                disabled={Boolean(busy)}
              >
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
                  disabled={Boolean(busy)}
                />
              </label>
              <FormStatus pending={Boolean(busy)} error={error} />
              <div className="form-actions">
                <button className="text-button" type="button" onClick={closeAction} disabled={Boolean(busy)}>
                  取消
                </button>
                <button
                  className="primary-button"
                  type="submit"
                  disabled={Boolean(busy) || actionReason.trim().length < 3}
                >
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
