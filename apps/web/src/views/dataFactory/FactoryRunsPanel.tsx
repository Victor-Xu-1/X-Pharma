import { ChevronLeft, ChevronRight, CircleStop, RotateCcw, Workflow } from "lucide-react";
import { formatDate, StatusBadge, statusLabel } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { IngestionRun } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";
import { RunStageSummary, runVersionProgressLabel } from "./RunStagePresentation";

export function FactoryRunsPanel({
  runs,
  page,
  pageSize,
  busy,
  editable,
  onPageChange,
  onOpen,
  onReplay,
  onCancel,
}: {
  runs: readonly IngestionRun[];
  page: number;
  pageSize: number;
  busy: boolean;
  editable: boolean;
  onPageChange: (page: number) => void;
  onOpen: (run: IngestionRun) => void;
  onReplay: (run: IngestionRun) => void;
  onCancel: (run: IngestionRun) => void;
}) {
  useLocale();
  const pages = Math.max(1, Math.ceil(runs.length / pageSize)),
    currentPage = Math.min(page, pages - 1);
  const visible = runs.slice(currentPage * pageSize, (currentPage + 1) * pageSize);
  return (
    <section aria-label={t("入库运行记录")}>
      <div className="section-header">
        <div>
          <h2>{t("入库运行记录")}</h2>
          <p>{t("扫描、快照、解析、投影和治理计数")}</p>
        </div>
      </div>
      {runs.length ? (
        <>
          <ScrollableTableRegion ariaLabel={t("入库运行记录")}>
            <table>
              <thead>
                <tr>
                  <th>{t("工作流")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("运行进度")}</th>
                  <th>{t("阶段")}</th>
                  <th>{t("心跳")}</th>
                  <th>{t("完成时间")}</th>
                  <th aria-label={t("操作")} />
                </tr>
              </thead>
              <tbody>
                {visible.map((run) => (
                  <tr key={run.id}>
                    <td className="mono-cell">{run.workflow_id}</td>
                    <td>
                      <StatusBadge value={run.effective_state} label={statusLabel(run.effective_state)} />
                    </td>
                    <td>
                      <div className="ingestion-run-progress">
                        <span>
                          <strong>{run.progress_percent}%</strong>
                          {runVersionProgressLabel(run)}
                        </span>
                        <progress
                          value={run.progress_percent}
                          max={100}
                          aria-label={t("{name} 运行进度", { name: run.workflow_id })}
                        />
                      </div>
                    </td>
                    <td>
                      <RunStageSummary run={run} />
                    </td>
                    <td>{formatDate(run.heartbeat_at, true)}</td>
                    <td>{formatDate(run.completed_at, true)}</td>
                    <td>
                      <div className="row-actions">
                        <button className="text-button" type="button" onClick={() => onOpen(run)}>
                          {t("运行详情")}
                        </button>
                        {editable && run.cancelable ? (
                          <button
                            className="icon-button"
                            type="button"
                            disabled={busy}
                            onClick={() => onCancel(run)}
                            title={t("取消运行")}
                            aria-label={t("取消 {name}", { name: run.workflow_id })}
                          >
                            <CircleStop size={15} />
                          </button>
                        ) : null}
                        {editable && ["failed", "partial", "canceled"].includes(run.state) ? (
                          <button
                            className="icon-button"
                            type="button"
                            disabled={busy}
                            onClick={() => onReplay(run)}
                            title={t("重放运行")}
                            aria-label={t("重放 {name}", { name: run.workflow_id })}
                          >
                            <RotateCcw size={15} />
                          </button>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          <nav className="factory-run-pagination" aria-label={t("入库运行记录分页")}>
            <span>
              {t("第 {page} / {pages} 页，共 {count} 条", { page: currentPage + 1, pages, count: runs.length })}
            </span>
            <div>
              <button
                className="icon-button"
                type="button"
                disabled={currentPage === 0}
                onClick={() => onPageChange(Math.max(0, currentPage - 1))}
                title={t("上一页")}
                aria-label={t("入库运行记录上一页")}
              >
                <ChevronLeft size={17} />
              </button>
              <button
                className="icon-button"
                type="button"
                disabled={currentPage >= pages - 1}
                onClick={() => onPageChange(Math.min(pages - 1, currentPage + 1))}
                title={t("下一页")}
                aria-label={t("入库运行记录下一页")}
              >
                <ChevronRight size={17} />
              </button>
            </div>
          </nav>
        </>
      ) : (
        <div className="factory-run-empty">
          <Workflow size={20} />
          <span>
            <strong>{t("暂无运行记录")}</strong>
            <small>{t("接入数据源后，自动扫描和治理结果会显示在这里。")}</small>
          </span>
        </div>
      )}
    </section>
  );
}
