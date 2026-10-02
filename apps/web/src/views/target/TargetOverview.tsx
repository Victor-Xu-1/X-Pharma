import { Activity, CalendarDays, FileCheck2, FileText, ShieldCheck } from "lucide-react";
import type { TargetDossier } from "../../lib/contracts/target";
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

const targetCoverageLabels: Record<string, string> = {
  relationships: "关系网络",
  evidence: "来源证据",
  target_evidence: "转化证据",
  activities: "活性数据",
  programs: "竞品管线",
  clinical_trials: "临床试验",
  patents: "专利",
  deals: "交易",
  regulatory_events: "监管动态",
  news_events: "新闻与会议",
  structures: "化学结构",
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
  const { profile, summary } = data;
  // Every landscape figure comes from the server summary, which aggregates the complete
  // authorized result set. The record collections on `data` are display-bounded and must
  // never be counted or re-classified in the browser.
  const phases = summary.phase_distribution ?? {};
  return (
    <div className="dossier-overview">
      <article className="narrative-section">
        <h3>功能摘要</h3>
        <p>{profile.function_summary ?? profile.entity.description ?? "暂无功能摘要。"}</p>
      </article>
      <div className="landscape-grid">
        <article>
          <Activity size={18} />
          <span>
            <strong>{summary.program_count}</strong>
            <small>研发项目</small>
          </span>
          <dl>
            {Object.entries(phases)
              .slice(0, 5)
              .map(([phase, count]) => (
                <div key={phase}>
                  <dt>{developmentPhaseLabel(phase)}</dt>
                  <dd>{count}</dd>
                </div>
              ))}
          </dl>
        </article>
        <article>
          <CalendarDays size={18} />
          <span>
            <strong>{summary.clinical_trial_count}</strong>
            <small>关联试验</small>
          </span>
          <p>{summary.recruiting_trial_count} 项处于招募状态</p>
          {summary.unclassified_trial_status_count > 0 ? (
            <small className="summary-gap-note">
              {summary.unclassified_trial_status_count} 项状态信息不完整，未计入招募统计
            </small>
          ) : null}
        </article>
        <article>
          <FileText size={18} />
          <span>
            <strong>{summary.patent_count}</strong>
            <small>专利族</small>
          </span>
          <p>{summary.active_patent_count} 项法律状态有效</p>
          {summary.unclassified_patent_status_count > 0 ? (
            <small className="summary-gap-note">
              {summary.unclassified_patent_status_count} 项状态信息不完整，未计入有效统计
            </small>
          ) : null}
        </article>
        <article>
          <FileCheck2 size={18} />
          <span>
            <strong>{summary.regulatory_event_count}</strong>
            <small>监管事件</small>
          </span>
          <p>{summary.approval_event_count} 项批准相关事件</p>
        </article>
      </div>
      {profile.sequence ? (
        <article className="sequence-section">
          <h3>蛋白序列</h3>
          <code>{profile.sequence}</code>
        </article>
      ) : null}
      <section className="coverage-section">
        <h3>关联信息</h3>
        <div className="coverage-grid">
          {data.coverage.map((item) => {
            const section = targetCoverageSections[item.domain];
            const opensEvidenceSearch = item.domain === "evidence" && Boolean(onOpenEvidence);
            const label = targetCoverageLabels[item.domain] ?? item.domain.replaceAll("_", " ");
            const note =
              item.status === "not_observed"
                ? "暂无可展示信息"
                : item.status === "truncated"
                  ? `${item.total} 条相关信息，当前显示 ${item.returned} 条`
                  : `${item.total} 条相关信息`;
            return (
              <article key={item.domain} className={item.status}>
                <span>{label}</span>
                <strong>{item.total}</strong>
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
                    查看{label}
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
