import { useQuery } from "@tanstack/react-query";
import { Eye, RotateCcw, X } from "lucide-react";
import { useState } from "react";
import { ErrorState, humanBytes, Spinner, StatusBadge } from "../../components/common";
import type { SourceVersion, SourceVersionReplayStage } from "../../lib/contracts/dataFactory";
import {
  dataFactoryKeys,
  loadSourceAsset,
  loadSourceVersionPreview,
  replaySourceVersion,
} from "../../lib/contracts/dataFactory";
import { useModalFocus } from "../../lib/useModalFocus";
import { ReplayVersionDialog, VERSION_REPLAY_STAGE_LABELS } from "./ReplayVersionDialog";

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
  const [replayBusy, setReplayBusy] = useState(false);
  const [replayError, setReplayError] = useState("");
  const [replayAccepted, setReplayAccepted] = useState("");
  const dialogRef = useModalFocus<HTMLElement>(true, onClose, { closeOnEscape: !replayBusy });
  const asset = useQuery({
    queryKey: dataFactoryKeys.asset(assetId),
    queryFn: ({ signal }) => loadSourceAsset(assetId, signal),
  });
  const preview = useQuery({
    queryKey: dataFactoryKeys.preview(previewVersionId ?? "none"),
    queryFn: ({ signal }) => loadSourceVersionPreview(previewVersionId ?? "", signal),
    enabled: Boolean(previewVersionId),
  });
  async function replayFailedVersion(operationKey: string, fromStage: SourceVersionReplayStage, reason: string) {
    if (!replayVersion) return;
    setReplayBusy(true);
    setReplayError("");
    try {
      const accepted = await replaySourceVersion(
        replayVersion.id,
        operationKey,
        replayVersion.state,
        replayVersion.errorCode,
        fromStage,
        reason,
      );
      setReplayAccepted(accepted.workflow_id);
      setReplayVersion(null);
    } catch (caught) {
      setReplayError(caught instanceof Error ? caught.message : "源版本重放失败");
    } finally {
      setReplayBusy(false);
    }
  }

  return (
    <div className="drawer-backdrop">
      <button
        className="drawer-dismiss"
        type="button"
        onClick={onClose}
        aria-label="关闭源对象详情"
        disabled={replayBusy}
      />
      <aside
        ref={dialogRef}
        className="detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="source-asset-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">SOURCE ASSET</p>
            <h2 id="source-asset-title">{asset.data?.file_name ?? "源对象版本"}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            title="关闭"
            aria-label="关闭源对象详情"
            disabled={replayBusy}
          >
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          {asset.isPending ? <Spinner label="正在读取源对象版本" /> : null}
          {asset.error instanceof Error ? (
            <ErrorState message={asset.error.message} retry={() => void asset.refetch()} />
          ) : null}
          {asset.data ? (
            <>
              {replayAccepted ? (
                <div className="factory-warning" role="status">
                  <RotateCcw size={17} />
                  <span>
                    <strong>版本重放已提交</strong>
                    工作流 <span className="mono-cell">{replayAccepted}</span> 已按指定恢复点提交处理。
                  </span>
                </div>
              ) : null}
              <dl className="enterprise-tenant-details">
                <div>
                  <dt>逻辑路径</dt>
                  <dd className="mono-cell">{asset.data.logical_path}</dd>
                </div>
                <div>
                  <dt>媒体类型</dt>
                  <dd>{asset.data.media_type ?? asset.data.extension}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{asset.data.state}</dd>
                </div>
                <div>
                  <dt>处理方式</dt>
                  <dd>{asset.data.processing_mode === "parse" ? "真实解析" : "仅登记资产"}</dd>
                </div>
              </dl>
              <section className="drawer-section">
                <h3>不可变版本</h3>
                <div className="source-version-list">
                  {asset.data.versions.map((version) => {
                    const replayableStages = version.replayable_stages ?? [];
                    return (
                      <article key={version.id}>
                        <header>
                          <strong>版本 {version.version_number}</strong>
                          <StatusBadge value={version.state} />
                        </header>
                        <dl>
                          <div>
                            <dt>SHA-256</dt>
                            <dd className="mono-cell">{version.content_sha256}</dd>
                          </div>
                          <div>
                            <dt>大小</dt>
                            <dd>{humanBytes(version.size_bytes)}</dd>
                          </div>
                          <div>
                            <dt>恶意文件扫描</dt>
                            <dd>{version.malware_scan_status}</dd>
                          </div>
                          <div>
                            <dt>解析 / 投影 / 治理</dt>
                            <dd>
                              {version.parse_status} / {version.retrieval_status} / {version.governance_status}
                            </dd>
                          </div>
                          <div>
                            <dt>解析器</dt>
                            <dd>
                              {version.parser_name
                                ? `${version.parser_name} ${version.parser_version ?? ""}`
                                : "未解析"}
                            </dd>
                          </div>
                        </dl>
                        {version.error_message ? <p className="source-error">{version.error_message}</p> : null}
                        {version.extracted_text_sha256 && version.error_code !== "malware_detected" ? (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => setPreviewVersionId(version.id)}
                          >
                            <Eye size={15} />
                            查看解析文本
                          </button>
                        ) : null}
                        {canManage && replayableStages.length > 0 ? (
                          <button
                            className="secondary-button"
                            type="button"
                            onClick={() => {
                              setReplayError("");
                              setReplayVersion({
                                id: version.id,
                                versionNumber: version.version_number,
                                state: version.state,
                                errorCode: version.error_code,
                                stages: replayableStages,
                              });
                            }}
                          >
                            <RotateCcw size={15} />
                            {replayableStages.length > 1
                              ? "选择恢复阶段"
                              : `从${VERSION_REPLAY_STAGE_LABELS[replayableStages[0]]}阶段重放`}
                          </button>
                        ) : null}
                      </article>
                    );
                  })}
                </div>
              </section>
              {previewVersionId ? (
                <section className="drawer-section" aria-labelledby="source-preview-title">
                  <h3 id="source-preview-title">解析文本预览</h3>
                  {preview.isPending ? <Spinner label="正在读取解析文本" /> : null}
                  {preview.error instanceof Error ? (
                    <ErrorState message={preview.error.message} retry={() => void preview.refetch()} />
                  ) : null}
                  {preview.data ? (
                    <>
                      <p className="field-help mono-cell">SHA-256 {preview.data.extracted_text_sha256}</p>
                      <pre className="source-text-preview">{preview.data.text}</pre>
                      {preview.data.truncated ? <p className="field-help">预览已按安全字符上限截断</p> : null}
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
            if (!replayBusy) {
              setReplayError("");
              setReplayVersion(null);
            }
          }}
          onConfirm={replayFailedVersion}
        />
      ) : null}
    </div>
  );
}
