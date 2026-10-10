import { Trash2 } from "lucide-react";
import { EmptyState, formatDate, humanBytes } from "../../../components/common";
import { ScrollableTableRegion } from "../../../components/ScrollableTableRegion";
import type { DataExportJob } from "../../../lib/contracts/commercial";
import { useLocale } from "../../../lib/i18n";
import { commercialLifecycleText as t } from "../../../lib/i18n/commercialLifecycle";
import type { LifecycleAction } from "./types";
export function LifecyclePurgeRecords({
  candidates,
  busy,
  beginAction,
}: {
  candidates: DataExportJob[];
  busy: string;
  beginAction: (action: LifecycleAction) => void;
}) {
  useLocale();
  return (
    <>
      <section className="operations-section">
        <header>
          <div>
            <p className="eyebrow">PURGE CANDIDATES</p>
            <h2>{t("到期导出对象")}</h2>
          </div>
        </header>
        {!candidates.length ? (
          <EmptyState title={t("暂无符合策略的清除候选项")} />
        ) : (
          <ScrollableTableRegion className="commercial-table" ariaLabel={t("到期导出对象滚动区域")}>
            <table aria-label={t("到期导出对象")}>
              <thead>
                <tr>
                  <th>{t("任务")}</th>
                  <th>{t("数据集")}</th>
                  <th>{t("文件大小")}</th>
                  <th>{t("到期时间")}</th>
                  <th>{t("操作")}</th>
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
                        title={t("清除到期对象")}
                        aria-label={t("清除到期对象 {id}", { id: job.id })}
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
    </>
  );
}
