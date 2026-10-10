import { RotateCcw, Trash2 } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { DeletedSourceAsset, SourceAssetImpact } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import { RecordDetails, RecordFacts, RecordList } from "../RecordDetails";
import type { LifecycleAction } from "./types";
export function LifecycleSourceRecords({
  sourceCandidates,
  deletedSourceAssets,
  busy,
  beginAction,
}: {
  sourceCandidates: SourceAssetImpact[];
  deletedSourceAssets: DeletedSourceAsset[];
  busy: string;
  beginAction: (action: LifecycleAction) => void;
}) {
  useLocale();
  return (
    <>
      <section className="operations-section" data-lifecycle="source-withdrawal">
        <header>
          <div>
            <h2>{t("源资料撤回候选")}</h2>
          </div>
        </header>
        {!sourceCandidates.length ? (
          <EmptyState title={t("暂无超过保留期的缺失源资料")} />
        ) : (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("源资料撤回候选滚动区域")}>
            <table aria-label={t("源资料撤回候选")}>
              <thead>
                <tr>
                  <th>{t("资料")}</th>
                  <th>{t("缺失时间")}</th>
                  <th>{t("依赖影响")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {sourceCandidates.map((asset) => (
                  <tr key={asset.id}>
                    <td>
                      <strong>{asset.file_name}</strong>
                      <span className="cell-subtitle mono-cell">{asset.logical_path}</span>
                      <RecordDetails name={asset.id}>
                        <RecordFacts
                          fields={[
                            { label: "标识", value: asset.id },
                            { label: "原始资料源标识", value: asset.data_source_id },
                            { label: "原始资料路径", value: asset.logical_path },
                            { label: "原始资料状态", value: asset.state },
                            { label: "资料版本", value: asset.version_count },
                            { label: "原始对象", value: asset.raw_object_count },
                            { label: "提取对象", value: asset.extracted_object_count },
                            { label: "提取运行", value: asset.extraction_run_count },
                            { label: "暂存事实", value: asset.staged_fact_count },
                            { label: "已发布事实", value: asset.published_fact_count },
                            { label: "证据声明", value: asset.evidence_claim_count },
                            { label: "知识引用", value: asset.knowledge_citation_count },
                            { label: "检索投影", value: asset.retrieval_projection_count },
                            { label: "共享文档", value: asset.shared_document_count },
                            { label: "其他文档引用", value: asset.other_document_reference_count },
                            { label: "阻断项", value: <RecordList values={asset.blockers} /> },
                          ]}
                        />
                      </RecordDetails>
                    </td>
                    <td>{asset.missing_since ? formatDate(asset.missing_since, true) : "--"}</td>
                    <td>
                      {t("{versions} 个版本 / {facts} 个治理事实", {
                        versions: asset.version_count,
                        facts: asset.staged_fact_count,
                      })}
                      <span className="cell-subtitle">
                        {asset.blockers.length ? asset.blockers.join(", ") : t("当前未返回阻断项")}
                      </span>
                    </td>
                    <td>
                      <StatusBadge
                        value={
                          asset.blockers.length ? "blocked" : asset.retention_eligible ? "eligible" : "not_eligible"
                        }
                        label={t(
                          asset.blockers.length
                            ? "已阻断"
                            : asset.retention_eligible
                              ? "本次读取符合保留期"
                              : "本次读取不符合保留期",
                        )}
                      />
                    </td>
                    <td>
                      <button
                        className="icon-button danger-text"
                        type="button"
                        title={asset.blockers.length ? t("存在业务依赖，执行后将记录阻断事件") : t("撤回源资料")}
                        aria-label={t("撤回源资料 {name}", { name: asset.file_name })}
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
            <h2>{t("已撤回源资料")}</h2>
          </div>
        </header>
        {!deletedSourceAssets.length ? (
          <EmptyState title={t("暂无等待重新授权的源资料")} />
        ) : (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("已撤回源资料滚动区域")}>
            <table aria-label={t("已撤回源资料")}>
              <thead>
                <tr>
                  <th>{t("资料")}</th>
                  <th>{t("撤回时间")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("操作")}</th>
                </tr>
              </thead>
              <tbody>
                {deletedSourceAssets.map((asset) => (
                  <tr key={asset.id}>
                    <td>
                      <strong>{asset.file_name}</strong>
                      <span className="cell-subtitle mono-cell">{asset.logical_path}</span>
                      <RecordDetails name={asset.id}>
                        <RecordFacts
                          fields={[
                            { label: "标识", value: asset.id },
                            { label: "原始资料源标识", value: asset.data_source_id },
                            { label: "原始资料路径", value: asset.logical_path },
                            { label: "原始资料状态", value: asset.state },
                          ]}
                        />
                      </RecordDetails>
                    </td>
                    <td>{formatDate(asset.updated_at, true)}</td>
                    <td>
                      <StatusBadge value={asset.state} />
                    </td>
                    <td>
                      <button
                        className="icon-button"
                        type="button"
                        title={t("重新授权并等待自动扫描")}
                        aria-label={t("重新授权源资料 {name}", { name: asset.file_name })}
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
    </>
  );
}
