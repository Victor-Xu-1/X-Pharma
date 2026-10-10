import { StatusBadge, statusLabel } from "../../components/common";
import type { IngestionRun } from "../../lib/contracts/dataFactory";
import { useLocale } from "../../lib/i18n";
import { factoryText as t } from "../../lib/i18n/dataFactory";

const RUN_STAGE_LABELS = {
  discovery: "发现",
  snapshot: "快照",
  malware_scan: "安全扫描",
  parse: "解析",
  retrieval: "检索投影",
  governance: "AI 治理",
} as const;

export function runStageLabel(stage: string): string {
  return Object.hasOwn(RUN_STAGE_LABELS, stage) ? t(RUN_STAGE_LABELS[stage as keyof typeof RUN_STAGE_LABELS]) : stage;
}

export function RunStageSummary({ run }: { run: IngestionRun }) {
  useLocale();
  const stages = run.stages
    .map((stage) => t("{stage}：{status}", { stage: runStageLabel(stage.stage), status: statusLabel(stage.status) }))
    .join("; ");
  return (
    <div
      className="ingestion-stage-summary"
      role="img"
      aria-label={`${t("{name} 阶段摘要", { name: run.workflow_id })}: ${stages}`}
    >
      {run.stages.map((stage) => (
        <span
          key={stage.stage}
          className={`stage-indicator ${stage.status}`}
          title={t("{stage}：{status}", { stage: runStageLabel(stage.stage), status: statusLabel(stage.status) })}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

export function RunStageGraph({ run }: { run: IngestionRun }) {
  useLocale();
  return (
    <section className="ingestion-stage-graph" aria-labelledby="run-stage-title">
      <header>
        <div>
          <h3 id="run-stage-title">{t("逐阶段运行图")}</h3>
          <p>
            {t("总进度 {percent}% · {versions}", {
              percent: run.progress_percent,
              versions: runVersionProgressLabel(run),
            })}
          </p>
        </div>
        <StatusBadge value={run.effective_state} />
      </header>
      <ol>
        {run.stages.map((stage) => (
          <li key={stage.stage} className={stage.status}>
            <span className="stage-node" aria-hidden="true" />
            <div>
              <strong>{runStageLabel(stage.stage)}</strong>
              <small>
                {stage.total_items
                  ? t("{complete} 完成 / {failed} 失败 / {total} 总计", {
                      complete: stage.completed_items,
                      failed: stage.failed_items,
                      total: stage.total_items,
                    })
                  : t(
                      stage.status === "not_started" || stage.status === "running"
                        ? "等待阶段输入"
                        : "本次没有待处理版本",
                    )}
              </small>
            </div>
            <StatusBadge value={stage.status} />
          </li>
        ))}
      </ol>
    </section>
  );
}

export function runVersionProgressLabel(run: IngestionRun): string {
  if (run.total_versions > 0) {
    return t("{complete}/{total} 个版本完成", { complete: run.completed_versions, total: run.total_versions });
  }
  const discovered = Math.max(
    0,
    run.counters.discovered ?? 0,
    run.stages.find((stage) => stage.stage === "discovery")?.total_items ?? 0,
  );
  if (run.effective_state === "pending" || run.effective_state === "running") {
    return t("正在发现版本 · 已观测 {count} 个对象", { count: discovered });
  }
  if (run.effective_state !== "succeeded") {
    return t("本次版本处理未完成 · 已观测 {count} 个对象", { count: discovered });
  }
  return discovered > 0 ? t("已检查 {count} 个对象 · 本次无新增版本", { count: discovered }) : t("本次无新增版本");
}
