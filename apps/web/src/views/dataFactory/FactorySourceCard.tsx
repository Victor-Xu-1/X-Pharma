import { CloudDownload, FolderSync, Pause, Pencil, Play, RefreshCw, ShieldCheck } from "lucide-react";
import { formatDate, humanBytes, StatusBadge } from "../../components/common";
import type { DataSource, DataSourceReadiness, IngestionCapabilities } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import { SourceSyncStatus } from "./SourceSyncStatus";
import {
  sourceOperationalLabel,
  sourceReadinessGuidance,
  sourceReadinessRawDiagnostic,
} from "./sourceReadinessPresentation";

export type FactorySourceAction = "scan" | "pause" | "resume";

export function FactorySourceCard({
  source,
  readiness,
  capabilities,
  busy,
  editable,
  onAction,
  onEdit,
}: {
  source: DataSource;
  readiness?: DataSourceReadiness;
  capabilities?: IngestionCapabilities;
  busy: boolean;
  editable: boolean;
  onAction: (source: DataSource, action: FactorySourceAction) => void;
  onEdit: (source: DataSource) => void;
}) {
  useLocale();
  const scanEnabled = capabilities?.durable_workflows_enabled === true && readiness?.configuration_ready === true;
  const scanReason =
    capabilities?.durable_workflows_enabled !== true
      ? "自动扫描工作流尚未启用"
      : readiness?.configuration_ready !== true
        ? "请先完成数据源治理配置"
        : "立即扫描";
  const state = readiness?.operational_status ?? source.state;
  return (
    <article>
      <div className="source-icon">
        {source.source_type === "folder" ? <FolderSync size={21} /> : <CloudDownload size={21} />}
      </div>
      <div className="source-core">
        <div>
          <h3>{source.name}</h3>
          <StatusBadge value={state} label={sourceOperationalLabel(state)} />
        </div>
        <p className="mono-cell">{source.root_uri}</p>
        <SourceSyncStatus readiness={readiness} />
        <details className="factory-source-details">
          <summary>{t("治理配置与来源信息")}</summary>
          <dl>
            <div>
              <dt>{t("数据集")}</dt>
              <dd>{source.dataset_key}</dd>
            </div>
            <div>
              <dt>{t("扫描周期")}</dt>
              <dd>{source.scan_interval_seconds}s</dd>
            </div>
            <div>
              <dt>{t("数据负责人")}</dt>
              <dd>{source.owner}</dd>
            </div>
            <div>
              <dt>{t("数据分级")}</dt>
              <dd>{source.data_classification}</dd>
            </div>
            <div>
              <dt>{t("授权期限")}</dt>
              <dd>
                {source.authorization_valid_until ? formatDate(source.authorization_valid_until, true) : t("长期有效")}
              </dd>
            </div>
            <div>
              <dt>{t("文件上限")}</dt>
              <dd>{humanBytes(source.max_file_bytes)}</dd>
            </div>
            <div>
              <dt>{t("最近成功")}</dt>
              <dd>{formatDate(source.last_success_at, true)}</dd>
            </div>
          </dl>
          {readiness ? (
            <div className="counter-row">
              <span>
                <ShieldCheck size={13} /> {readiness.connector_id ?? t("未识别连接器")}
              </span>
              <span>{readiness.delivery_channels.join(" + ") || t("无交付许可")}</span>
              <span>{t(readiness.cursor_present ? "已建立增量游标" : "等待首次游标")}</span>
            </div>
          ) : null}
        </details>
        {sourceRecordRows(readiness?.checks.filter((check) => check.status !== "pass") ?? []).map(
          ({ key, value: check }) => (
            <p className="source-error" key={key}>
              {sourceReadinessGuidance(check, readiness?.freshness_age_seconds ?? null)}
              {sourceReadinessRawDiagnostic(check, readiness?.freshness_age_seconds ?? null) ? (
                <small>{sourceReadinessRawDiagnostic(check, readiness?.freshness_age_seconds ?? null)}</small>
              ) : null}
            </p>
          ),
        )}
        {capabilities?.durable_workflows_enabled === false ? (
          <p className="source-error">{t("自动扫描工作流尚未启用；完成平台运行配置后才能执行扫描。")}</p>
        ) : null}
        {source.last_error ? <p className="source-error">{source.last_error}</p> : null}
      </div>
      {editable ? (
        <div className="row-actions">
          <button
            className="icon-button"
            type="button"
            disabled={busy || !scanEnabled}
            onClick={() => onAction(source, "scan")}
            title={t(scanReason)}
            aria-label={t("立即扫描 {name}", { name: source.name })}
          >
            <RefreshCw size={17} />
          </button>
          <button
            className="icon-button"
            type="button"
            disabled={busy}
            onClick={() => onEdit(source)}
            title={t("编辑治理配置")}
            aria-label={t("编辑 {name}", { name: source.name })}
          >
            <Pencil size={16} />
          </button>
          {source.state === "paused" ? (
            <button
              className="icon-button"
              type="button"
              disabled={busy}
              onClick={() => onAction(source, "resume")}
              title={t("恢复")}
              aria-label={t("恢复 {name}", { name: source.name })}
            >
              <Play size={17} />
            </button>
          ) : (
            <button
              className="icon-button"
              type="button"
              disabled={busy}
              onClick={() => onAction(source, "pause")}
              title={t("暂停")}
              aria-label={t("暂停 {name}", { name: source.name })}
            >
              <Pause size={17} />
            </button>
          )}
        </div>
      ) : null}
    </article>
  );
}
