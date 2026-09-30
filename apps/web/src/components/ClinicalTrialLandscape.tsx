import { BarChart3, List } from "lucide-react";

import type { ClinicalTrialLandscapeMatrixRowRead, ClinicalTrialLandscapeRead } from "../lib/generated";
import { biomedicalChartPalette } from "./chartPalette";

type MatrixView = "chart" | "table";
type FilterField = "phase" | "result_evaluation";

const phaseColumns = [
  { key: "EARLY_PHASE1", label: "早期 I 期", color: biomedicalChartPalette.trialPhase.earlyPhase1 },
  { key: "PHASE1", label: "I 期", color: biomedicalChartPalette.trialPhase.phase1 },
  { key: "PHASE1_PHASE2", label: "I/II 期", color: biomedicalChartPalette.trialPhase.phase12 },
  { key: "PHASE2", label: "II 期", color: biomedicalChartPalette.trialPhase.phase2 },
  { key: "PHASE2_PHASE3", label: "II/III 期", color: biomedicalChartPalette.trialPhase.phase23 },
  { key: "PHASE3", label: "III 期", color: biomedicalChartPalette.trialPhase.phase3 },
  { key: "PHASE4", label: "IV 期", color: biomedicalChartPalette.trialPhase.phase4 },
  { key: "NA", label: "不适用", color: biomedicalChartPalette.trialPhase.notApplicable },
  { key: "__missing__", label: "未披露", color: biomedicalChartPalette.trialPhase.missing },
] as const;

const evaluationColumns = [
  { key: "unfavorable", label: "不佳", color: biomedicalChartPalette.evaluation.unfavorable },
  { key: "not_superior", label: "非优", color: biomedicalChartPalette.evaluation.notSuperior },
  { key: "non_inferior", label: "非劣", color: biomedicalChartPalette.evaluation.nonInferior },
  { key: "similar", label: "相似", color: biomedicalChartPalette.evaluation.similar },
  { key: "positive", label: "积极", color: biomedicalChartPalette.evaluation.positive },
  { key: "superior", label: "优效", color: biomedicalChartPalette.evaluation.superior },
  { key: "terminated", label: "终止", color: biomedicalChartPalette.evaluation.terminated },
  { key: "__missing__", label: "未评价", color: biomedicalChartPalette.evaluation.missing },
] as const;

type MatrixColumn = { key: string; label: string; color: string };

function phaseLabel(value: string) {
  return phaseColumns.find((column) => column.key === value)?.label ?? value;
}

function MatrixSection({
  id,
  title,
  detail,
  rows,
  columns,
  rowLabel,
  filterField,
  onFilter,
  view,
  onViewChange,
}: {
  id: string;
  title: string;
  detail: string;
  rows: ClinicalTrialLandscapeMatrixRowRead[];
  columns: readonly MatrixColumn[];
  rowLabel: (key: string) => string;
  filterField: FilterField;
  onFilter: (field: FilterField, value: string) => void;
  view: MatrixView;
  onViewChange: (view: MatrixView) => void;
}) {
  return (
    <section className="trial-landscape-section" aria-labelledby={`${id}-title`}>
      <header>
        <div>
          <h3 id={`${id}-title`}>{title}</h3>
          <p>{detail}</p>
        </div>
        <fieldset className="segmented-control trial-landscape-view-toggle">
          <legend className="sr-only">{title}展示方式</legend>
          <button type="button" aria-pressed={view === "chart"} onClick={() => onViewChange("chart")}>
            <BarChart3 size={14} />
            图示
          </button>
          <button type="button" aria-pressed={view === "table"} onClick={() => onViewChange("table")}>
            <List size={14} />
            列表
          </button>
        </fieldset>
      </header>
      <fieldset className="trial-landscape-legend">
        <legend className="sr-only">{title}图例</legend>
        {columns.map((column) => (
          <button
            type="button"
            key={column.key}
            disabled={column.key === "__missing__"}
            onClick={() => onFilter(filterField, column.key)}
            title={column.key === "__missing__" ? undefined : `按${column.label}筛选`}
          >
            <span style={{ backgroundColor: column.color }} aria-hidden="true" />
            {column.label}
          </button>
        ))}
      </fieldset>
      {rows.length ? (
        view === "chart" ? (
          <div className="trial-landscape-chart" role="img" aria-label={`${title}完整命中集分布`}>
            {rows.map((row) => (
              <div className="trial-landscape-chart-row" key={row.key}>
                <span>{rowLabel(row.key)}</span>
                <div className="trial-landscape-chart-track">
                  {columns.map((column) => {
                    const count = row.values?.[column.key] ?? 0;
                    if (!count || !row.total) return null;
                    return (
                      <i
                        key={column.key}
                        style={{ backgroundColor: column.color, width: `${(count / row.total) * 100}%` }}
                        title={`${rowLabel(row.key)} · ${column.label}: ${count}`}
                      />
                    );
                  })}
                </div>
                <strong>{row.total.toLocaleString()}</strong>
              </div>
            ))}
          </div>
        ) : (
          <div className="trial-landscape-table-wrap">
            <table className="trial-landscape-table" aria-label={`${title}统计表`}>
              <thead>
                <tr>
                  <th scope="col">{id === "publication-year-phase" ? "披露年份" : "试验阶段"}</th>
                  {columns.map((column) => (
                    <th scope="col" key={column.key}>
                      {column.label}
                    </th>
                  ))}
                  <th scope="col">总计</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{rowLabel(row.key)}</th>
                    {columns.map((column) => (
                      <td key={column.key}>{(row.values?.[column.key] ?? 0).toLocaleString()}</td>
                    ))}
                    <td>{row.total.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        <p className="trial-landscape-empty" role="status" aria-live="polite" aria-atomic="true">
          当前授权命中集没有可统计的数据。
        </p>
      )}
    </section>
  );
}

export function ClinicalTrialLandscape({
  landscape,
  onFilter,
  view,
  onViewChange,
}: {
  landscape: ClinicalTrialLandscapeRead;
  onFilter: (field: FilterField, value: string) => void;
  view: MatrixView;
  onViewChange: (view: MatrixView) => void;
}) {
  return (
    <section className="trial-landscape" aria-label="临床结果可视化">
      <header className="trial-landscape-summary">
        <div>
          <span>完整命中集</span>
          <strong>{landscape.total_trials.toLocaleString()}</strong>
          <small>项临床试验</small>
        </div>
        <p>统计与当前筛选、租户授权和数据时点一致，不受当前分页影响。</p>
      </header>
      <MatrixSection
        id="publication-year-phase"
        title="试验数量"
        detail="按最近结果披露年份与试验阶段交叉统计"
        rows={landscape.publication_year_phase ?? []}
        columns={phaseColumns}
        rowLabel={(key) => (key === "__missing__" ? "未披露" : key)}
        filterField="phase"
        onFilter={onFilter}
        view={view}
        onViewChange={onViewChange}
      />
      <MatrixSection
        id="phase-evaluation"
        title="总体评价"
        detail="按试验阶段与最优结果评价交叉统计"
        rows={landscape.phase_evaluation ?? []}
        columns={evaluationColumns}
        rowLabel={phaseLabel}
        filterField="result_evaluation"
        onFilter={onFilter}
        view={view}
        onViewChange={onViewChange}
      />
    </section>
  );
}
