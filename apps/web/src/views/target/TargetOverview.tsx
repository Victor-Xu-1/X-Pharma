import { Activity, CalendarDays, FileCheck2, FileText, ShieldCheck } from "lucide-react";
import type { TargetDossier } from "../../lib/contracts/target";
import { formattingLocale, useMessages } from "../../lib/i18n";
import { targetCoverageLabelKeys, targetDossierMessages } from "../../lib/i18n/targetDossier";
import type { TargetDossierSection } from "../../lib/workspaceRouting";
import { developmentPhaseLabel } from "./pipeline/presentation";

const targetCoverageSections: Partial<Record<string, TargetDossierSection>> = {
  relationships: "relationships",
  target_evidence: "evidence",
  activities: "activities",
  programs: "pipeline",
  clinical_trials: "trials",
  patents: "patents",
  deals: "deals",
  regulatory_events: "regulatory",
  news_events: "news",
  structures: "structures",
};

export function Overview({
  data,
  onOpenSection,
  onOpenEvidence,
}: {
  data: TargetDossier;
  onOpenSection: (section: TargetDossierSection) => void;
  onOpenEvidence?: (query: string) => void;
}) {
  const text = useMessages(targetDossierMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const { profile, summary } = data;
  // Every landscape figure comes from the server summary, which aggregates the complete
  // authorized result set. The record collections on `data` are display-bounded and must
  // never be counted or re-classified in the browser.
  const phases = summary.phase_distribution ?? {};
  return (
    <div className="dossier-overview">
      <article className="narrative-section">
        <h3>{text("功能摘要")}</h3>
        <p>{profile.function_summary ?? profile.entity.description ?? text("暂无功能摘要。")}</p>
      </article>
      <div className="landscape-grid">
        <article>
          <Activity size={18} />
          <span>
            <strong>{number.format(summary.program_count)}</strong>
            <small>{text("研发项目")}</small>
          </span>
          <dl>
            {Object.entries(phases)
              .slice(0, 5)
              .map(([phase, count]) => (
                <div key={phase}>
                  <dt>{developmentPhaseLabel(phase)}</dt>
                  <dd>{number.format(count)}</dd>
                </div>
              ))}
          </dl>
        </article>
        <article>
          <CalendarDays size={18} />
          <span>
            <strong>{number.format(summary.clinical_trial_count)}</strong>
            <small>{text("关联试验")}</small>
          </span>
          <p>{text("{count} 项处于招募状态", { count: number.format(summary.recruiting_trial_count) })}</p>
          {summary.unclassified_trial_status_count > 0 ? (
            <small className="summary-gap-note">
              {text("{count} 项状态信息不完整，未计入招募统计", {
                count: number.format(summary.unclassified_trial_status_count),
              })}
            </small>
          ) : null}
        </article>
        <article>
          <FileText size={18} />
          <span>
            <strong>{number.format(summary.patent_count)}</strong>
            <small>{text("专利族")}</small>
          </span>
          <p>{text("{count} 项法律状态有效", { count: number.format(summary.active_patent_count) })}</p>
          {summary.unclassified_patent_status_count > 0 ? (
            <small className="summary-gap-note">
              {text("{count} 项状态信息不完整，未计入有效统计", {
                count: number.format(summary.unclassified_patent_status_count),
              })}
            </small>
          ) : null}
        </article>
        <article>
          <FileCheck2 size={18} />
          <span>
            <strong>{number.format(summary.regulatory_event_count)}</strong>
            <small>{text("监管事件")}</small>
          </span>
          <p>{text("{count} 项批准相关事件", { count: number.format(summary.approval_event_count) })}</p>
        </article>
      </div>
      {profile.sequence ? (
        <article className="sequence-section">
          <h3>{text("蛋白序列")}</h3>
          <code>{profile.sequence}</code>
        </article>
      ) : null}
      <section className="coverage-section">
        <h3>{text("关联信息")}</h3>
        <div className="coverage-grid">
          {data.coverage.map((item) => {
            const section = Object.hasOwn(targetCoverageSections, item.domain)
              ? targetCoverageSections[item.domain]
              : undefined;
            const opensEvidenceSearch = item.domain === "evidence" && Boolean(onOpenEvidence);
            const label = Object.hasOwn(targetCoverageLabelKeys, item.domain)
              ? text(targetCoverageLabelKeys[item.domain as keyof typeof targetCoverageLabelKeys])
              : item.domain.replaceAll("_", " ");
            const note =
              item.status === "not_observed"
                ? text("暂无可展示信息")
                : item.status === "truncated"
                  ? text("{total} 条相关信息，当前显示 {returned} 条", {
                      total: number.format(item.total),
                      returned: number.format(item.returned),
                    })
                  : text("{total} 条相关信息", { total: number.format(item.total) });
            return (
              <article key={item.domain} className={item.status}>
                <span>{label}</span>
                <strong>{number.format(item.total)}</strong>
                <small>{note}</small>
                {section || opensEvidenceSearch ? (
                  <button
                    className="coverage-open-button"
                    type="button"
                    disabled={item.total === 0}
                    onClick={() =>
                      opensEvidenceSearch ? onOpenEvidence?.(profile.entity.name) : onOpenSection(section ?? "overview")
                    }
                  >
                    {text("查看{label}", { label })}
                  </button>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
      {data.warnings?.map((warning) => (
        <p className="inline-alert" key={warning}>
          <ShieldCheck size={15} /> {warning}
        </p>
      ))}
    </div>
  );
}
