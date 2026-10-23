import type { DataSource } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { SourceRoutingFields } from "./SourceRoutingFields";
import type { SourceEditorDraft } from "./sourceEditorDraft";
import { isPublicResearchSource, sourceRequiresCredential } from "./sourceRules";

export type SourceEditorChange = <K extends keyof SourceEditorDraft>(key: K, value: SourceEditorDraft[K]) => void;
const sourceLabels = {
  folder: "服务端固定只读目录",
  pubmed: "PubMed（元数据索引）",
  clinicaltrials_gov: "ClinicalTrials.gov（自动增量）",
  chembl: "ChEMBL（目标与机制）",
  http_manifest: "HTTP Manifest API",
  s3_snapshot: "S3 只读快照",
  sftp_snapshot: "SFTP 只读快照",
  smb_snapshot: "SMB / NAS 只读快照",
} as const;
const rootLabels = {
  folder: "服务端只读目录",
  http_manifest: "Manifest API 地址",
  pubmed: "PubMed API 地址",
  clinicaltrials_gov: "ClinicalTrials.gov API 地址",
  chembl: "ChEMBL API 地址",
  s3_snapshot: "S3 Bucket / Prefix",
  sftp_snapshot: "SFTP 目录地址",
  smb_snapshot: "SMB 共享目录地址",
} as const;

export function SourceConnectionFields({
  draft,
  change,
  changeType,
  changeAbstract,
  allowedRoots,
  editing,
  durable,
}: {
  draft: SourceEditorDraft;
  change: SourceEditorChange;
  changeType: (type: DataSource["source_type"]) => void;
  changeAbstract: (include: boolean) => void;
  allowedRoots: readonly string[];
  editing: boolean;
  durable: boolean;
}) {
  useLocale();
  const type = draft.sourceType;
  const rootLabel = Object.hasOwn(rootLabels, type) ? t(rootLabels[type]) : type;
  return (
    <div className="source-form-section">
      <header>
        <strong>{t("连接配置")}</strong>
        <small>{t(durable ? "数据源注册后立即进入自动调度" : "数据源登记后将在工作流服务启用时进入自动调度")}</small>
      </header>
      <div className="source-form-grid">
        <label>
          <span>{t("数据源名称")}</span>
          <input
            value={draft.name}
            onChange={(event) => change("name", event.target.value)}
            required
            maxLength={200}
            data-modal-autofocus="true"
          />
        </label>
        {!editing ? (
          <label>
            <span>{t("数据源类型")}</span>
            <select value={type} onChange={(event) => changeType(event.target.value as DataSource["source_type"])}>
              {Object.entries(sourceLabels).map(([value, label]) => (
                <option key={value} value={value}>
                  {t(label)}
                </option>
              ))}
            </select>
          </label>
        ) : null}
        <div className="source-path-field">
          <label htmlFor="source-root-uri">{rootLabel}</label>
          <input
            id="source-root-uri"
            value={draft.rootUri}
            onChange={(event) => change("rootUri", event.target.value)}
            required
            disabled={editing || isPublicResearchSource(type)}
            list={type === "folder" ? "allowed-folder-roots" : undefined}
          />
          {type === "folder" && allowedRoots.length ? (
            <datalist id="allowed-folder-roots">
              {allowedRoots.map((root) => (
                <option key={root} value={root} />
              ))}
            </datalist>
          ) : null}
          {type === "folder" ? (
            <small className="field-help">
              {t("允许根目录：{roots}", { roots: allowedRoots.join(" / ") || t("部署环境尚未配置") })}
            </small>
          ) : null}
        </div>
        {isPublicResearchSource(type) ? (
          <SourceRoutingFields
            sourceType={type}
            draft={draft.routing}
            onChange={(value) => change("routing", { ...draft.routing, ...value })}
            onAbstractChange={changeAbstract}
          />
        ) : null}
        {sourceRequiresCredential(type) ? (
          <label>
            <span>{t(editing ? "新凭据引用" : "凭据引用")}</span>
            <input
              value={draft.credentialRef}
              onChange={(event) => change("credentialRef", event.target.value)}
              required={!editing && type !== "s3_snapshot"}
              placeholder={
                type === "http_manifest"
                  ? "env://SUPPLIER_API_TOKEN"
                  : type === "s3_snapshot"
                    ? "env://SUPPLIER_S3_CREDENTIALS_JSON"
                    : type === "sftp_snapshot"
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
  );
}
