import { ArrowLeft, CalendarDays } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../../components/ResearchTabList";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { ClinicalTrialDetailRead } from "../../lib/generated";
import { formattingLocale } from "../../lib/i18n";
import { clinicalCaption, clinicalText as t } from "../../lib/i18n/clinical";
import { localizedTrialPhase, localizedTrialStatus } from "../../lib/i18n/trialVocabulary";
import type { TrialDossierSection } from "../../lib/workspaceRouting";
import { displayList } from "./presentation";
import { TrialDesign } from "./TrialDesign";
import { TrialOutcomes } from "./TrialOutcomes";
import { TrialOverview } from "./TrialOverview";
import { TrialTimeline } from "./TrialTimeline";
import type { TrialEntityOpener } from "./viewTypes";

const trialDetailTabs: Array<ResearchTabOption<TrialDossierSection>> = [
  { key: "overview", label: "概览" },
  { key: "design", label: "设计与入组" },
  { key: "outcomes", label: "终点与结果" },
  { key: "timeline", label: "时间线与中心" },
];

export function TrialProfessionalDossier({
  trialId,
  data,
  loading,
  error,
  activeSection,
  onRetry,
  onBack,
  onSectionChange,
  onOpenTrialEntity,
  onOpenProvenance,
}: {
  trialId: string;
  data: ClinicalTrialDetailRead | undefined;
  loading: boolean;
  error: Error | null;
  activeSection: TrialDossierSection;
  onRetry: () => void;
  onBack?: () => void;
  onSectionChange: (section: TrialDossierSection, replace?: boolean) => void;
  onOpenTrialEntity: TrialEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  return (
    <section className="trial-professional-page" aria-labelledby="trial-title">
      {onBack ? (
        <button className="trial-back-button" type="button" onClick={onBack}>
          <ArrowLeft size={16} aria-hidden="true" />
          {t("返回试验列表")}
        </button>
      ) : null}
      <header className="trial-professional-header">
        <div className="trial-professional-symbol">
          <CalendarDays size={23} />
        </div>
        <div className="trial-professional-identity">
          <span>
            {t("临床试验专业档案")} · {data ? `${data.registry_name} · ${data.registry_id}` : trialId}
          </span>
          <h2 id="trial-title">{data?.official_title ?? t("临床试验专业档案")}</h2>
          <p>{data ? displayList(data.conditions, t("适应症未记录"), 6) : t("正在恢复临床试验深链接")}</p>
        </div>
        {data ? (
          <div>
            <StatusBadge value={data.overall_status ?? "UNKNOWN"} label={localizedTrialStatus(data.overall_status)} />
          </div>
        ) : null}
      </header>

      {loading ? <Spinner label={t("正在加载临床试验专业档案")} /> : null}
      {error ? <ErrorState message={error.message || t("临床试验专业档案加载失败")} retry={onRetry} /> : null}
      {data ? (
        <>
          <dl className="dossier-metrics trial-professional-metrics">
            <div>
              <dt>{t("临床分期")}</dt>
              <dd>{displayList(data.phases.map(localizedTrialPhase), t("未记录"))}</dd>
            </div>
            <div>
              <dt>{t("招募状态")}</dt>
              <dd>{localizedTrialStatus(data.overall_status)}</dd>
            </div>
            <div>
              <dt>{t("入组人数")}</dt>
              <dd>{data.enrollment?.toLocaleString(formattingLocale()) ?? "--"}</dd>
            </div>
            <div>
              <dt>{t("结果状态")}</dt>
              <dd>{data.has_results ? t("已发布") : t("未发布")}</dd>
            </div>
            <div>
              <dt>{t("关键结果")}</dt>
              <dd>{data.key_result_count ?? 0}</dd>
            </div>
            <div>
              <dt>{t("最近更新")}</dt>
              <dd>{formatDate(data.last_update_posted)}</dd>
            </div>
          </dl>
          <ResearchTabList
            tabs={trialDetailTabs.map((tab) => ({ ...tab, label: clinicalCaption(tab.label) }))}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel={t("临床试验专业档案分区")}
            idPrefix="trial-dossier"
          />
          <div
            className="trial-professional-body"
            id={`trial-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`trial-dossier-tab-${activeSection}`}
          >
            {activeSection === "overview" ? <TrialOverview data={data} onOpenEntity={onOpenTrialEntity} /> : null}
            {activeSection === "design" ? <TrialDesign data={data} /> : null}
            {activeSection === "outcomes" ? <TrialOutcomes data={data} /> : null}
            {activeSection === "timeline" ? <TrialTimeline data={data} /> : null}
          </div>
          <footer className="trial-detail-footer">
            <span>{t("数据更新 {date}", { date: formatDate(data.last_update_posted, true) })}</span>
            <ProvenanceButton
              selection={{ resourceType: "clinical_trial", resourceId: data.id, label: data.registry_id }}
              onOpen={onOpenProvenance}
            />
          </footer>
        </>
      ) : null}
    </section>
  );
}
