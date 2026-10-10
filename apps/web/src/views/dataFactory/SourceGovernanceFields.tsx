import type { DataSource, DataSourceDataset } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import type { SourceEditorChange } from "./SourceConnectionFields";
import type { SourceEditorDraft } from "./sourceEditorDraft";

export function SourceGovernanceFields({
  draft,
  change,
  datasets,
  source,
}: {
  draft: SourceEditorDraft;
  change: SourceEditorChange;
  datasets: readonly DataSourceDataset[];
  source?: DataSource;
}) {
  useLocale();
  return (
    <div className="source-form-section">
      <header>
        <strong>{t("数据治理")}</strong>
        <small>{t("负责人、授权和用途决定数据是否允许发布")}</small>
      </header>
      <div className="source-form-grid">
        <label>
          <span>{t("数据负责人")}</span>
          <input
            value={draft.owner}
            onChange={(event) => change("owner", event.target.value)}
            required
            maxLength={200}
          />
        </label>
        <label>
          <span>{t("数据分级")}</span>
          <select
            value={draft.classification}
            onChange={(event) => change("classification", event.target.value as SourceEditorDraft["classification"])}
          >
            <option value="public">{t("公开")}</option>
            <option value="internal">{t("内部")}</option>
            <option value="confidential">{t("机密")}</option>
            <option value="restricted">{t("受限")}</option>
          </select>
        </label>
        <label className="source-path-field">
          <span>{t("授权范围编号（每行一个）")}</span>
          <textarea
            value={draft.authorizationScopes}
            onChange={(event) => change("authorizationScopes", event.target.value)}
            required
            maxLength={12000}
          />
        </label>
        <label>
          <span>{t("授权生效时间")}</span>
          <input
            type="datetime-local"
            value={draft.authorizationValidFrom}
            onChange={(event) => change("authorizationValidFrom", event.target.value)}
            required
          />
        </label>
        <label>
          <span>{t("授权结束时间（留空表示长期有效）")}</span>
          <input
            type="datetime-local"
            value={draft.authorizationValidUntil}
            min={draft.authorizationValidFrom}
            onChange={(event) => change("authorizationValidUntil", event.target.value)}
          />
        </label>
        <label>
          <span>{t("目标数据集")}</span>
          <select
            value={draft.datasetKey}
            onChange={(event) => change("datasetKey", event.target.value)}
            required
            disabled={Boolean(source)}
          >
            {source && !datasets.some((dataset) => dataset.dataset_key === source.dataset_key) ? (
              <option value={source.dataset_key}>{source.dataset_key}</option>
            ) : null}
            {datasets.map((dataset) => (
              <option key={dataset.dataset_key} value={dataset.dataset_key}>
                {dataset.display_name} · {dataset.license_id}/{dataset.license_policy_version}
              </option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}

export function SourceAutomationFields({ draft, change }: { draft: SourceEditorDraft; change: SourceEditorChange }) {
  useLocale();
  return (
    <div className="source-form-section">
      <header>
        <strong>{t("自动化策略")}</strong>
        <small>{t("持续增量扫描，不移动或修改源文件")}</small>
      </header>
      <div className="source-form-grid compact">
        <label>
          <span>{t("扫描周期（秒）")}</span>
          <input
            type="number"
            min={10}
            max={86400}
            value={draft.interval}
            onChange={(event) => change("interval", Number(event.target.value))}
            required
          />
        </label>
        <label>
          <span>{t("Freshness 目标（秒）")}</span>
          <input
            type="number"
            min={60}
            max={31536000}
            value={draft.freshness}
            onChange={(event) => change("freshness", Number(event.target.value))}
            required
          />
        </label>
      </div>
    </div>
  );
}
