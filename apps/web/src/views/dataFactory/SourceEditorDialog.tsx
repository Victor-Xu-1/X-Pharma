import { X } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import type { DataSource, DataSourceDataset } from "../../lib/contracts/dataFactory";
import { createDataSource, updateDataSource } from "../../lib/contracts/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";
import { SourceRoutingFields } from "./SourceRoutingFields";
import {
  initialPublicSourceDraft,
  isPublicResearchSource,
  PUBLIC_RESEARCH_SOURCES,
  sourceRequiresCredential,
  sourceRootLabel,
  sourceRoutingRules,
  toLocalDateTimeInput,
} from "./sourceRules";

export function SourceEditorDialog({
  datasets,
  allowedFolderRoots,
  durableWorkflowsEnabled,
  source,
  onClose,
  onCreated,
}: {
  datasets: DataSourceDataset[];
  allowedFolderRoots: string[];
  durableWorkflowsEnabled: boolean;
  source?: DataSource;
  onClose: () => void;
  onCreated: () => Promise<void>;
}) {
  const eligibleDatasets = datasets.filter((dataset) => dataset.active && dataset.license_current);
  const [sourceType, setSourceType] = useState<DataSource["source_type"]>(source?.source_type ?? "folder");
  const [name, setName] = useState(source?.name ?? "");
  const [rootUri, setRootUri] = useState(source?.root_uri ?? allowedFolderRoots[0] ?? "/sources/knowledge");
  const [credentialRef, setCredentialRef] = useState("");
  const [owner, setOwner] = useState(source?.owner ?? "");
  const [authorizationScopes, setAuthorizationScopes] = useState(source?.authorization_scopes.join("\n") ?? "");
  const [authorizationValidFrom, setAuthorizationValidFrom] = useState(
    toLocalDateTimeInput(source?.authorization_valid_from),
  );
  const [authorizationValidUntil, setAuthorizationValidUntil] = useState(
    source?.authorization_valid_until ? toLocalDateTimeInput(source.authorization_valid_until) : "",
  );
  const [classification, setClassification] = useState<"public" | "internal" | "confidential" | "restricted">(
    source?.data_classification ?? "internal",
  );
  const [datasetKey, setDatasetKey] = useState(source?.dataset_key ?? eligibleDatasets[0]?.dataset_key ?? "");
  const [interval, setInterval] = useState(source?.scan_interval_seconds ?? 300);
  const [freshness, setFreshness] = useState(source?.expected_freshness_seconds ?? 86400);
  const [sourceDraft, setSourceDraft] = useState(() => initialPublicSourceDraft(source));
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const locked = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const dialogRef = useModalFocus<HTMLElement>(true, () => {
    if (!locked.current) onClose();
  });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (locked.current) return;
    locked.current = true;
    setSubmitting(true);
    setError("");
    try {
      const validFrom = new Date(authorizationValidFrom);
      const validUntil = authorizationValidUntil ? new Date(authorizationValidUntil) : null;
      if (Number.isNaN(validFrom.getTime())) throw new Error("授权生效时间无效");
      if (validUntil && (Number.isNaN(validUntil.getTime()) || validUntil <= validFrom)) {
        throw new Error("授权结束时间必须晚于生效时间");
      }
      const routingRules = sourceRoutingRules(sourceType, sourceDraft);
      const governance = {
        name: name.trim(),
        owner: owner.trim(),
        data_classification: classification,
        authorization_scopes: authorizationScopes
          .split(/\r?\n|,/)
          .map((scope) => scope.trim())
          .filter(Boolean),
        authorization_valid_from: validFrom.toISOString(),
        authorization_valid_until: validUntil?.toISOString() ?? null,
        scan_interval_seconds: interval,
        expected_freshness_seconds: freshness,
      };
      if (source) {
        await updateDataSource(source.id, {
          ...governance,
          ...(isPublicResearchSource(source.source_type) ? { routing_rules: routingRules } : {}),
          ...(sourceRequiresCredential(source.source_type) && credentialRef.trim()
            ? { credential_ref: credentialRef.trim() }
            : {}),
        });
      } else
        await createDataSource({
          ...governance,
          source_type: sourceType,
          root_uri: rootUri.trim(),
          ...(isPublicResearchSource(sourceType) ? { routing_rules: routingRules } : {}),
          ...(sourceRequiresCredential(sourceType) && credentialRef.trim()
            ? { credential_ref: credentialRef.trim() }
            : {}),
          dataset_key: datasetKey,
          include_globs: ["*", "**/*"],
          exclude_globs: [],
          stable_seconds: sourceType === "folder" ? 30 : 0,
          max_file_bytes: 1073741824,
          rate_limit_per_minute: 60,
        });
      if (mounted.current) await onCreated();
    } catch (caught) {
      if (mounted.current) setError(caught instanceof Error ? caught.message : "注册失败");
    } finally {
      locked.current = false;
      if (mounted.current) setSubmitting(false);
    }
  }
  return (
    <div className="modal-backdrop" role="presentation">
      <section
        ref={dialogRef}
        className="modal-panel source-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="create-source-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">DATA SOURCE</p>
            <h2 id="create-source-title">{source ? "编辑数据源治理配置" : "接入自动数据源"}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            disabled={submitting}
            title="关闭"
            aria-label="关闭"
          >
            <X size={18} />
          </button>
        </header>
        <form onSubmit={submit}>
          <div className="source-form-section">
            <header>
              <strong>连接配置</strong>
              <small>
                {durableWorkflowsEnabled
                  ? "数据源注册后立即进入自动调度"
                  : "数据源登记后将在工作流服务启用时进入自动调度"}
              </small>
            </header>
            <div className="source-form-grid">
              <label>
                <span>数据源名称</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  required
                  maxLength={200}
                  data-modal-autofocus="true"
                />
              </label>
              {!source ? (
                <label>
                  <span>数据源类型</span>
                  <select
                    value={sourceType}
                    onChange={(event) => {
                      const nextType = event.target.value as DataSource["source_type"];
                      setSourceType(nextType);
                      if (isPublicResearchSource(nextType)) {
                        const publicSource = PUBLIC_RESEARCH_SOURCES[nextType];
                        const preferredDatasetKey =
                          nextType === "pubmed" ? "literature" : nextType === "chembl" ? "chembl" : "clinical_trials";
                        setRootUri(publicSource.rootUri);
                        setClassification("public");
                        setAuthorizationScopes(publicSource.authorizationScope);
                        if (eligibleDatasets.some((dataset) => dataset.dataset_key === preferredDatasetKey)) {
                          setDatasetKey(preferredDatasetKey);
                        }
                        setSourceDraft(initialPublicSourceDraft());
                      } else {
                        setRootUri(
                          nextType === "folder"
                            ? (allowedFolderRoots[0] ?? "/sources/knowledge")
                            : nextType === "http_manifest"
                              ? "https://supplier.example/v1/manifest"
                              : nextType === "s3_snapshot"
                                ? "s3://licensed-supplier/research/"
                                : nextType === "sftp_snapshot"
                                  ? "sftp://supplier.example:22/delivery/"
                                  : "smb://fileserver.example:445/research/delivery/",
                        );
                      }
                      setCredentialRef("");
                    }}
                  >
                    <option value="folder">服务端固定只读目录</option>
                    <option value="pubmed">PubMed（元数据索引）</option>
                    <option value="clinicaltrials_gov">ClinicalTrials.gov（自动增量）</option>
                    <option value="chembl">ChEMBL（目标与机制）</option>
                    <option value="http_manifest">HTTP Manifest API</option>
                    <option value="s3_snapshot">S3 只读快照</option>
                    <option value="sftp_snapshot">SFTP 只读快照</option>
                    <option value="smb_snapshot">SMB / NAS 只读快照</option>
                  </select>
                </label>
              ) : null}
              <div className="source-path-field">
                <label htmlFor="source-root-uri">{sourceRootLabel(sourceType)}</label>
                <input
                  id="source-root-uri"
                  value={rootUri}
                  onChange={(event) => setRootUri(event.target.value)}
                  required
                  disabled={Boolean(source) || isPublicResearchSource(sourceType)}
                  list={sourceType === "folder" ? "allowed-folder-roots" : undefined}
                />
                {sourceType === "folder" && allowedFolderRoots.length ? (
                  <datalist id="allowed-folder-roots">
                    {allowedFolderRoots.map((root) => (
                      <option key={root} value={root} />
                    ))}
                  </datalist>
                ) : null}
                {sourceType === "folder" ? (
                  <small className="field-help">
                    允许根目录：{allowedFolderRoots.join("、") || "部署环境尚未配置"}
                  </small>
                ) : null}
              </div>
              {isPublicResearchSource(sourceType) ? (
                <SourceRoutingFields
                  sourceType={sourceType}
                  draft={sourceDraft}
                  onChange={(change) => setSourceDraft((current) => ({ ...current, ...change }))}
                  onAbstractChange={(include) => {
                    setSourceDraft((current) => ({ ...current, includeAbstract: include }));
                    setAuthorizationScopes((current) => {
                      const scope = "public:ncbi-pubmed-abstracts";
                      const scopes = current
                        .split(/\r?\n|,/)
                        .map((value) => value.trim())
                        .filter(Boolean)
                        .filter((value) => value !== scope);
                      if (include) scopes.push(scope);
                      return scopes.join("\n");
                    });
                  }}
                />
              ) : null}
              {sourceRequiresCredential(sourceType) ? (
                <label>
                  <span>{source ? "新凭据引用" : "凭据引用"}</span>
                  <input
                    value={credentialRef}
                    onChange={(event) => setCredentialRef(event.target.value)}
                    required={!source && sourceType !== "s3_snapshot"}
                    placeholder={
                      sourceType === "http_manifest"
                        ? "env://SUPPLIER_API_TOKEN"
                        : sourceType === "s3_snapshot"
                          ? "env://SUPPLIER_S3_CREDENTIALS_JSON"
                          : sourceType === "sftp_snapshot"
                            ? "env://SUPPLIER_SFTP_CREDENTIALS_JSON"
                            : "env://ENTERPRISE_SMB_CREDENTIALS_JSON"
                    }
                    maxLength={500}
                    autoComplete="off"
                  />
                </label>
              ) : null}
            </div>
          </div>

          <div className="source-form-section">
            <header>
              <strong>数据治理</strong>
              <small>负责人、授权和用途决定数据是否允许发布</small>
            </header>
            <div className="source-form-grid">
              <label>
                <span>数据负责人</span>
                <input value={owner} onChange={(event) => setOwner(event.target.value)} required maxLength={200} />
              </label>
              <label>
                <span>数据分级</span>
                <select
                  value={classification}
                  onChange={(event) => setClassification(event.target.value as typeof classification)}
                >
                  <option value="public">公开</option>
                  <option value="internal">内部</option>
                  <option value="confidential">机密</option>
                  <option value="restricted">受限</option>
                </select>
              </label>
              <label className="source-path-field">
                <span>授权范围编号（每行一个）</span>
                <textarea
                  value={authorizationScopes}
                  onChange={(event) => setAuthorizationScopes(event.target.value)}
                  required
                  maxLength={12000}
                />
              </label>
              <label>
                <span>授权生效时间</span>
                <input
                  type="datetime-local"
                  value={authorizationValidFrom}
                  onChange={(event) => setAuthorizationValidFrom(event.target.value)}
                  required
                />
              </label>
              <label>
                <span>授权结束时间（留空表示长期有效）</span>
                <input
                  type="datetime-local"
                  value={authorizationValidUntil}
                  min={authorizationValidFrom}
                  onChange={(event) => setAuthorizationValidUntil(event.target.value)}
                />
              </label>
              <label>
                <span>目标数据集</span>
                <select
                  value={datasetKey}
                  onChange={(event) => setDatasetKey(event.target.value)}
                  required
                  disabled={Boolean(source)}
                >
                  {source && !eligibleDatasets.some((dataset) => dataset.dataset_key === source.dataset_key) ? (
                    <option value={source.dataset_key}>{source.dataset_key}</option>
                  ) : null}
                  {eligibleDatasets.map((dataset) => (
                    <option key={dataset.dataset_key} value={dataset.dataset_key}>
                      {dataset.display_name} · {dataset.license_id}/{dataset.license_policy_version}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <div className="source-form-section">
            <header>
              <strong>自动化策略</strong>
              <small>持续增量扫描，不移动或修改源文件</small>
            </header>
            <div className="source-form-grid compact">
              <label>
                <span>扫描周期（秒）</span>
                <input
                  type="number"
                  min={10}
                  max={86400}
                  value={interval}
                  onChange={(event) => setInterval(Number(event.target.value))}
                  required
                />
              </label>
              <label>
                <span>Freshness 目标（秒）</span>
                <input
                  type="number"
                  min={60}
                  max={31536000}
                  value={freshness}
                  onChange={(event) => setFreshness(Number(event.target.value))}
                  required
                />
              </label>
            </div>
          </div>
          {!source && !eligibleDatasets.length ? (
            <p className="form-error" role="alert">
              当前没有已启用且许可有效的数据集
            </p>
          ) : null}
          {error ? (
            <p className="form-error" role="alert">
              {error}
            </p>
          ) : null}
          <div className="form-actions">
            <button className="text-button" type="button" onClick={onClose} disabled={submitting}>
              取消
            </button>
            <button
              className="primary-button"
              type="submit"
              disabled={submitting || (!source && !eligibleDatasets.length)}
            >
              {submitting ? "保存中" : source ? "保存" : "注册"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
