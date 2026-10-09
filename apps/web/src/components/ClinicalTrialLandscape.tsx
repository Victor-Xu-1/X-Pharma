import { BarChart3, List } from "lucide-react";

import type { ClinicalTrialLandscapeMatrixRowRead, ClinicalTrialLandscapeRead } from "../lib/generated";
import { formattingLocale, useLocale } from "../lib/i18n";
import { clinicalText as t } from "../lib/i18n/clinical";
import { professionalEnumLabel } from "../lib/i18n/professionalEnums";
import { localizedTrialPhase } from "../lib/i18n/trialVocabulary";
import { trialResultEvaluationLabels } from "../lib/trialFilters";
import { chartPalette } from "./chartPalette";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

type MatrixView = "chart" | "table";
type FilterField = "phase" | "result_evaluation";

const phaseColumns = [
  { key: "EARLY_PHASE1", color: chartPalette.trialPhase.earlyPhase1 },
  { key: "PHASE1", color: chartPalette.trialPhase.phase1 },
  { key: "PHASE1_PHASE2", color: chartPalette.trialPhase.phase12 },
  { key: "PHASE2", color: chartPalette.trialPhase.phase2 },
  { key: "PHASE2_PHASE3", color: chartPalette.trialPhase.phase23 },
  { key: "PHASE3", color: chartPalette.trialPhase.phase3 },
  { key: "PHASE4", color: chartPalette.trialPhase.phase4 },
  { key: "NA", color: chartPalette.trialPhase.notApplicable },
  { key: "__missing__", color: chartPalette.trialPhase.missing },
] as const;

const evaluationColumns = [
  { key: "unfavorable", color: chartPalette.evaluation.unfavorable },
  { key: "not_superior", color: chartPalette.evaluation.notSuperior },
  { key: "non_inferior", color: chartPalette.evaluation.nonInferior },
  { key: "similar", color: chartPalette.evaluation.similar },
  { key: "positive", color: chartPalette.evaluation.positive },
  { key: "superior", color: chartPalette.evaluation.superior },
  { key: "terminated", color: chartPalette.evaluation.terminated },
  { key: "__missing__", color: chartPalette.evaluation.missing },
] as const;

type MatrixColumn = { key: string; label: string; color: string; filterable: boolean };

function phaseLabel(value: string) {
  return value === "__missing__" ? t("未披露") : localizedTrialPhase(value);
}

function matrixColumns(rows: ClinicalTrialLandscapeMatrixRowRead[], field: FilterField): MatrixColumn[] {
  const palette = field === "phase" ? phaseColumns : evaluationColumns;
  const keys = new Set(palette.map((column) => column.key as string));
  const unknown = [...new Set(rows.flatMap((row) => Object.keys(row.values ?? {})))]
    .filter((key) => !keys.has(key))
    .sort();
  return [...palette, ...unknown.map((key) => ({ key, color: chartPalette.trialPhase.missing }))].map((column) => {
    const known = Object.hasOwn(trialResultEvaluationLabels, column.key);
    const caption = known
      ? trialResultEvaluationLabels[column.key as keyof typeof trialResultEvaluationLabels]
      : column.key;
    return {
      ...column,
      label:
        field === "phase"
          ? phaseLabel(column.key)
          : column.key === "__missing__"
            ? t("未评价")
            : known
              ? professionalEnumLabel(caption, column.key)
              : column.key,
      // The evaluation API is an enum: observed unknown codes remain visible but are not valid filters.
      filterable: column.key !== "__missing__" && (field === "phase" || known),
    };
  });
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
          <legend className="sr-only">{t("{title}展示方式", { title })}</legend>
          <button type="button" aria-pressed={view === "chart"} onClick={() => onViewChange("chart")}>
            <BarChart3 size={14} />
            {t("图示")}
          </button>
          <button type="button" aria-pressed={view === "table"} onClick={() => onViewChange("table")}>
            <List size={14} />
            {t("列表")}
          </button>
        </fieldset>
      </header>
      <fieldset className="trial-landscape-legend">
        <legend className="sr-only">{t("{title}图例", { title })}</legend>
        {columns.map((column) => (
          <button
            type="button"
            key={column.key}
            disabled={!column.filterable}
            onClick={() => onFilter(filterField, column.key)}
            title={column.filterable ? t("按{label}筛选", { label: column.label }) : undefined}
          >
            <span style={{ backgroundColor: column.color }} aria-hidden="true" />
            {column.label}
          </button>
        ))}
      </fieldset>
      {rows.length ? (
        view === "chart" ? (
          <div className="trial-landscape-chart" role="img" aria-label={t("{title}完整命中集分布", { title })}>
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
                <strong>{row.total.toLocaleString(formattingLocale())}</strong>
              </div>
            ))}
          </div>
        ) : (
          <ScrollableTableRegion className="trial-landscape-table-wrap" ariaLabel={t("{title}统计表", { title })}>
            <table className="trial-landscape-table" aria-label={t("{title}统计表", { title })}>
              <thead>
                <tr>
                  <th scope="col">{id === "publication-year-phase" ? t("披露年份") : t("试验阶段")}</th>
                  {columns.map((column) => (
                    <th scope="col" key={column.key}>
                      {column.label}
                    </th>
                  ))}
                  <th scope="col">{t("总计")}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{rowLabel(row.key)}</th>
                    {columns.map((column) => (
                      <td key={column.key}>{(row.values?.[column.key] ?? 0).toLocaleString(formattingLocale())}</td>
                    ))}
                    <td>{row.total.toLocaleString(formattingLocale())}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        )
      ) : (
        <p className="trial-landscape-empty" role="status" aria-live="polite" aria-atomic="true">
          {t("当前授权命中集没有可统计的数据。")}
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
  useLocale();
  return (
    <section className="trial-landscape" aria-label={t("临床结果可视化")}>
      <header className="trial-landscape-summary">
        <div>
          <span>{t("完整命中集")}</span>
          <strong>{landscape.total_trials.toLocaleString(formattingLocale())}</strong>
          <small>{t("项临床试验")}</small>
        </div>
        <p>{t("统计与当前筛选、租户授权和数据时点一致，不受当前分页影响。")}</p>
      </header>
      <p className="trial-detail-note">{t("同一试验可登记多个阶段；阶段分配数不等于独立试验数。")}</p>
      <MatrixSection
        id="publication-year-phase"
        title={t("试验数量")}
        detail={t("按最近结果披露年份与试验阶段交叉统计")}
        rows={landscape.publication_year_phase ?? []}
        columns={matrixColumns(landscape.publication_year_phase ?? [], "phase")}
        rowLabel={(key) => (key === "__missing__" ? t("未披露") : key)}
        filterField="phase"
        onFilter={onFilter}
        view={view}
        onViewChange={onViewChange}
      />
      <MatrixSection
        id="phase-evaluation"
        title={t("总体评价")}
        detail={t("按试验阶段与最优结果评价交叉统计")}
        rows={landscape.phase_evaluation ?? []}
        columns={matrixColumns(landscape.phase_evaluation ?? [], "result_evaluation")}
        rowLabel={phaseLabel}
        filterField="result_evaluation"
        onFilter={onFilter}
        view={view}
        onViewChange={onViewChange}
      />
    </section>
  );
}
