import { StatusBadge } from "../../components/common";
import type { IngestionRun } from "../../lib/contracts/dataFactory";

export const RUN_STAGE_LABELS: Record<IngestionRun["stages"][number]["stage"], string> = {
  discovery: "发现",
  snapshot: "快照",
  malware_scan: "安全扫描",
  parse: "解析",
  retrieval: "检索投影",
  governance: "AI 治理",
};

export function RunStageSummary({ run }: { run: IngestionRun }) {
  return (
    <div className="ingestion-stage-summary" role="img" aria-label={`${run.workflow_id} 阶段摘要`}>
      {run.stages.map((stage) => (
        <span
          key={stage.stage}
          className={`stage-indicator ${stage.status}`}
          title={`${RUN_STAGE_LABELS[stage.stage]}：${stage.status}`}
          aria-hidden="true"
        />
      ))}
    </div>
  );
}

export function RunStageGraph({ run }: { run: IngestionRun }) {
  return (
    <section className="ingestion-stage-graph" aria-labelledby="run-stage-title">
      <header>
        <div>
          <h3 id="run-stage-title">逐阶段运行图</h3>
          <p>
            总进度 {run.progress_percent}% · {runVersionProgressLabel(run)}
          </p>
        </div>
        <StatusBadge value={run.effective_state} />
      </header>
      <ol>
        {run.stages.map((stage) => (
          <li key={stage.stage} className={stage.status}>
            <span className="stage-node" aria-hidden="true" />
            <div>
              <strong>{RUN_STAGE_LABELS[stage.stage]}</strong>
              <small>
                {stage.total_items
                  ? `${stage.completed_items} 完成 / ${stage.failed_items} 失败 / ${stage.total_items} 总计`
                  : "本次没有待处理版本"}
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
    return `${run.completed_versions}/${run.total_versions} 个版本完成`;
  }
  const discovered = Math.max(
    0,
    run.counters.discovered ?? 0,
    run.stages.find((stage) => stage.stage === "discovery")?.total_items ?? 0,
  );
  return discovered > 0 ? `已检查 ${discovered} 个对象 · 本次无新增版本` : "本次无新增版本";
}
