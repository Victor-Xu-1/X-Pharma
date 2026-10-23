import { useQuery } from "@tanstack/react-query";
import { RefreshCw, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { ErrorState, Spinner } from "../../components/common";
import { ApiError } from "../../lib/api";
import type { SourceVersion, SourceVersionReplayStage } from "../../lib/contracts/dataFactory";
import {
  dataFactoryKeys,
  loadSourceAsset,
  loadSourceVersionPreview,
  replaySourceVersion,
} from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";
import { ReplayVersionDialog } from "./ReplayVersionDialog";
import { SourceVersionCard } from "./SourceVersionCard";
import { useFactoryOperation } from "./useFactoryOperation";

export function SourceAssetDrawer({
  assetId,
  canManage,
  onClose,
}: {
  assetId: string;
  canManage: boolean;
  onClose: () => void;
}) {
  const [previewVersionId, setPreviewVersionId] = useState<string | null>(null);
  const [replayVersion, setReplayVersion] = useState<{
    id: string;
    versionNumber: number;
    state: SourceVersion["state"];
    errorCode: string | null;
    stages: SourceVersionReplayStage[];
  } | null>(null);
  useLocale();
  const operation = useFactoryOperation();
  const replayBusy = Boolean(operation.busy);
  const replayError = operation.error;
  const [replayAccepted, setReplayAccepted] = useState("");
  const dismiss = () => {
    if (!operation.isLocked()) onClose();
  };
  const dialogRef = useModalFocus<HTMLElement>(true, dismiss, { closeOnEscape: !replayBusy });
  const asset = useQuery({
    queryKey: dataFactoryKeys.asset(assetId),
    queryFn: ({ signal }) => loadSourceAsset(assetId, signal),
  });
  const preview = useQuery({
    queryKey: dataFactoryKeys.preview(previewVersionId ?? "none"),
    queryFn: ({ signal }) => loadSourceVersionPreview(previewVersionId ?? "", signal),
    enabled: Boolean(previewVersionId),
  });
  const denied = asset.error instanceof ApiError && [401, 403].includes(asset.error.status);
  const assetMismatch = Boolean(asset.data && asset.data.id !== assetId);
  const data = denied || assetMismatch ? undefined : asset.data;
  const previewDenied = preview.error instanceof ApiError && [401, 403].includes(preview.error.status);
  const previewMismatch = Boolean(preview.data && preview.data.source_version_id !== previewVersionId);
  const previewData = previewDenied || previewMismatch ? undefined : preview.data;

  async function replayFailedVersion(operationKey: string, fromStage: SourceVersionReplayStage, reason: string) {
    if (!replayVersion || !canManage || !data || asset.isError || asset.isFetching) return;
    await operation.execute(`version:${replayVersion.id}:replay`, "源版本重放失败", async (current) => {
      const accepted = await replaySourceVersion(
        replayVersion.id,
        operationKey,
        replayVersion.state,
        replayVersion.errorCode,
        fromStage,
        reason,
      );
      if (current()) {
        setReplayAccepted(accepted.workflow_id);
        setReplayVersion(null);
      }
    });
  }

  return (
    <div className="drawer-backdrop">
      <button
        className="drawer-dismiss"
        type="button"
        onClick={dismiss}
        aria-label={t("关闭源对象详情")}
        disabled={replayBusy}
      />
      <aside
        ref={dialogRef}
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-busy={replayBusy}
        aria-labelledby="source-asset-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <h2 id="source-asset-title">{data?.file_name ?? t("源对象版本")}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={() => void asset.refetch()}
            disabled={replayBusy || asset.isFetching}
            title={t("刷新源对象版本")}
            aria-label={t("刷新源对象版本")}
          >
            <RefreshCw size={18} aria-hidden="true" />
          </button>
          <button
            className="icon-button"
            type="button"
            onClick={dismiss}
            title={t("关闭")}
            aria-label={t("关闭源对象详情")}
            disabled={replayBusy}
          >
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          {asset.isPending ? <Spinner label={t("正在读取源对象版本")} /> : null}
          {asset.error instanceof Error ? (
            <ErrorState message={asset.error.message} retry={() => void asset.refetch()} />
          ) : null}
          {assetMismatch ? (
            <ErrorState message={t("源对象与请求标识不一致")} retry={() => void asset.refetch()} />
          ) : null}
          {data && asset.isError ? <p className="field-help">{t("上次读取的版本（非实时）")}</p> : null}
          {data ? (
            <>
              {replayAccepted ? (
                <div className="factory-warning" role="status">
                  <RotateCcw size={17} />
                  <span>
                    <strong>{t("版本重放已提交")}</strong>
                    {t("工作流 {id} 已按指定恢复点提交处理。", { id: replayAccepted })}
                  </span>
                </div>
              ) : null}
              <dl className="enterprise-tenant-details">
                <div>
                  <dt>{t("逻辑路径")}</dt>
                  <dd className="mono-cell">{data.logical_path}</dd>
                </div>
                <div>
                  <dt>{t("媒体类型")}</dt>
                  <dd>{data.media_type ?? data.extension}</dd>
                </div>
                <div>
                  <dt>{t("状态")}</dt>
                  <dd>{data.state}</dd>
                </div>
                <div>
                  <dt>{t("处理方式")}</dt>
                  <dd>
                    {data.processing_mode === "parse"
                      ? t("真实解析")
                      : data.processing_mode === "asset_only"
                        ? t("仅登记资产")
                        : data.processing_mode}
                  </dd>
                </div>
              </dl>
              <section className="drawer-section">
                <h3>{t("不可变版本")}</h3>
                <div className="source-version-list">
                  {!data.versions.length ? <p className="field-help">{t("暂无不可变版本")}</p> : null}
                  {data.versions.map((version) => (
                    <SourceVersionCard
                      key={version.id}
                      version={version}
                      canManage={canManage}
                      disabled={replayBusy || asset.isError || asset.isFetching}
                      onPreview={setPreviewVersionId}
                      onReplay={(version, stages) => {
                        operation.clear();
                        setReplayVersion({
                          id: version.id,
                          versionNumber: version.version_number,
                          state: version.state,
                          errorCode: version.error_code,
                          stages,
                        });
                      }}
                    />
                  ))}
                </div>
              </section>
              {previewVersionId ? (
                <section className="drawer-section" aria-labelledby="source-preview-title">
                  <h3 id="source-preview-title">{t("解析文本预览")}</h3>
                  {preview.isPending ? <Spinner label={t("正在读取解析文本")} /> : null}
                  {preview.error instanceof Error ? (
                    <ErrorState message={preview.error.message} retry={() => void preview.refetch()} />
                  ) : null}
                  {previewMismatch ? (
                    <ErrorState message={t("解析文本与请求版本不一致")} retry={() => void preview.refetch()} />
                  ) : null}
                  {previewData && preview.isError ? (
                    <p className="field-help">{t("上次读取的解析文本（非实时）")}</p>
                  ) : null}
                  {previewData ? (
                    <>
                      <p className="field-help mono-cell">SHA-256 {previewData.extracted_text_sha256}</p>
                      <pre className="source-text-preview">{previewData.text}</pre>
                      {previewData.truncated ? <p className="field-help">{t("预览已按安全字符上限截断")}</p> : null}
                    </>
                  ) : null}
                </section>
              ) : null}
            </>
          ) : null}
        </div>
      </aside>
      {replayVersion ? (
        <ReplayVersionDialog
          versionNumber={replayVersion.versionNumber}
          errorCode={replayVersion.errorCode}
          stages={replayVersion.stages}
          busy={replayBusy}
          error={replayError}
          onClose={() => {
            if (!operation.isLocked()) {
              operation.clear();
              setReplayVersion(null);
            }
          }}
          onConfirm={replayFailedVersion}
        />
      ) : null}
    </div>
  );
}
