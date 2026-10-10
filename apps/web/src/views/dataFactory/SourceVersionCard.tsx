import { Eye, RotateCcw } from "lucide-react";
import { humanBytes, StatusBadge } from "../../components/common";
import type { SourceVersion, SourceVersionReplayStage } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { versionReplayStageLabel } from "./ReplayVersionDialog";

export function SourceVersionCard({
  version,
  canManage,
  disabled,
  onPreview,
  onReplay,
}: {
  version: SourceVersion;
  canManage: boolean;
  disabled: boolean;
  onPreview: (id: string) => void;
  onReplay: (version: SourceVersion, stages: SourceVersionReplayStage[]) => void;
}) {
  useLocale();
  const stages = version.replayable_stages ?? [];
  return (
    <article>
      <header>
        <strong>{t("版本 {number}", { number: version.version_number })}</strong>
        <StatusBadge value={version.state} />
      </header>
      <dl>
        <div>
          <dt>SHA-256</dt>
          <dd className="mono-cell">{version.content_sha256}</dd>
        </div>
        <div>
          <dt>{t("大小")}</dt>
          <dd>{humanBytes(version.size_bytes)}</dd>
        </div>
        <div>
          <dt>{t("恶意文件扫描")}</dt>
          <dd>{version.malware_scan_status}</dd>
        </div>
        <div>
          <dt>{t("解析 / 投影 / 治理")}</dt>
          <dd>
            {version.parse_status} / {version.retrieval_status} / {version.governance_status}
          </dd>
        </div>
        <div>
          <dt>{t("解析器")}</dt>
          <dd>{version.parser_name ? `${version.parser_name} ${version.parser_version ?? ""}` : t("未解析")}</dd>
        </div>
      </dl>
      {version.error_message ? <p className="source-error">{version.error_message}</p> : null}
      {version.extracted_text_sha256 && version.error_code !== "malware_detected" ? (
        <button className="secondary-button" type="button" disabled={disabled} onClick={() => onPreview(version.id)}>
          <Eye size={15} aria-hidden="true" />
          {t("查看解析文本")}
        </button>
      ) : null}
      {canManage && stages.length > 0 ? (
        <button
          className="secondary-button"
          type="button"
          disabled={disabled}
          onClick={() => onReplay(version, stages)}
        >
          <RotateCcw size={15} aria-hidden="true" />
          {stages.length > 1
            ? t("选择恢复阶段")
            : t("从{stage}阶段重放", { stage: versionReplayStageLabel(stages[0]) })}
        </button>
      ) : null}
    </article>
  );
}
