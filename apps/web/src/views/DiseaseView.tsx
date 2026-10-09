import { useQuery } from "@tanstack/react-query";
import { Stethoscope } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList } from "../components/ResearchTabList";
import { diseaseKeys, loadDiseaseDossier } from "../lib/contracts/disease";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { isProviderLabel } from "../lib/entityPresentation";
import { useLocale } from "../lib/i18n";
import { type diseaseDossierMessages, diseaseDossierText as t } from "../lib/i18n/diseaseDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../lib/i18n/programVocabulary";
import type { Entity } from "../lib/types";
import type { DiseaseDossierSection } from "../lib/workspaceRouting";
import { DiseaseEvidence } from "./disease/DiseaseEvidence";
import { DiseaseOverview } from "./disease/DiseaseOverview";
import { EpidemiologyPanel } from "./disease/EpidemiologyPanel";
import { RegistryConditionDossier } from "./disease/RegistryConditionDossier";
import { tabs } from "./disease/vocabulary";
import {
  Deals,
  type DossierEntityOpener,
  News,
  Patents,
  Programs,
  Regulatory,
  Relationships,
  Trials,
} from "./EntityDossierView";

export function DiseaseView({
  disease,
  activeSection,
  onSectionChange,
  onOpenEpidemiology,
  onOpenEntity,
  onOpenDrug,
  onOpenTarget,
  onOpenDisease,
  onOpenOrganization,
  onOpenTrial,
  onOpenPatent,
  onOpenDeal,
  onOpenRegulatoryEvent,
  onOpenNewsEvent,
}: {
  disease: Entity | null;
  activeSection: DiseaseDossierSection;
  onSectionChange: (section: DiseaseDossierSection, replace?: boolean) => void;
  onOpenEpidemiology: (diseaseId: string) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (drugId: string) => void;
  onOpenTarget?: (targetId: string) => void;
  onOpenDisease?: (diseaseId: string) => void;
  onOpenOrganization?: (organizationId: string) => void;
  onOpenTrial: (trialId: string) => void;
  onOpenPatent: (patentId: string) => void;
  onOpenDeal: (dealId: string) => void;
  onOpenRegulatoryEvent: (eventId: string) => void;
  onOpenNewsEvent: (eventId: string) => void;
}) {
  useLocale();
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const dossier = useQuery({
    queryKey: diseaseKeys.dossier(disease?.id ?? ""),
    queryFn: ({ signal }) => loadDiseaseDossier(disease?.id ?? "", signal),
    enabled: Boolean(disease?.id && disease.entity_type === "disease"),
  });

  if (!disease)
    return <EmptyState title={t("尚未选择疾病")} detail={t("请从查询、管线或流行病学结果中打开疾病档案")} />;
  if (disease.entity_type !== "disease") {
    return <ErrorState message={t("该深链接不是疾病实体，无法打开疾病专业档案")} />;
  }
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : t("疾病档案加载失败")}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={t("正在加载 {name} 疾病档案", { name: disease.name })} />;
  if (dossier.data.entity.id !== disease.id || dossier.data.entity.entity_type !== "disease") {
    return <ErrorState message={t("疾病档案与请求实体不一致")} retry={() => void dossier.refetch()} />;
  }

  const data = dossier.data;
  const openDrug = onOpenDrug ?? onOpenEntity;
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const openDiseaseEntity: DossierEntityOpener = (entityType, entityId) => {
    switch (entityType) {
      case "drug":
        openDrug(entityId);
        return;
      case "target":
        openTarget(entityId);
        return;
      case "disease":
        openDisease(entityId);
        return;
      case "organization":
        openOrganization(entityId);
        return;
      default:
        onOpenEntity(entityId);
    }
  };
  return (
    <>
      {isProviderLabel(data.entity) ? (
        <RegistryConditionDossier
          data={data}
          activeSection={activeSection}
          onSectionChange={onSectionChange}
          onOpen={setProvenanceSelection}
          onOpenEntity={onOpenEntity}
          onOpenTypedEntity={openDiseaseEntity}
          onOpenTrial={onOpenTrial}
        />
      ) : (
        <section className="company-profile-page disease-profile-page">
          <header className="company-profile-header disease-profile-header">
            <div className="company-profile-symbol disease-profile-symbol">
              <Stethoscope size={23} />
            </div>
            <div className="company-profile-identity">
              <span>{t("疾病专业档案")}</span>
              <h2>{data.entity.name}</h2>
              <p>{data.entity.description ?? t("暂无疾病简介")}</p>
            </div>
          </header>

          <dl className="dossier-metrics company-profile-metrics">
            <div>
              <dt>{t("最高研发阶段")}</dt>
              <dd>{phaseLabel(data.summary.highest_phase)}</dd>
            </div>
            <div>
              <dt>{t("研发项目 / 药物")}</dt>
              <dd>
                {data.summary.program_count} / {data.summary.drug_count}
              </dd>
            </div>
            <div>
              <dt>{t("靶点 / 公司")}</dt>
              <dd>
                {data.summary.target_count} / {data.summary.organization_count}
              </dd>
            </div>
            <div>
              <dt>{t("疾病负担观测")}</dt>
              <dd>{data.summary.epidemiology_observation_count}</dd>
            </div>
            <div>
              <dt>{t("临床试验 / 专利")}</dt>
              <dd>
                {data.summary.clinical_trial_count} / {data.summary.patent_count}
              </dd>
            </div>
            <div>
              <dt>{t("最近活动")}</dt>
              <dd>{formatDate(data.summary.latest_activity_at)}</dd>
            </div>
          </dl>

          <ResearchTabList
            tabs={tabs.map((tab) => ({ ...tab, label: t(tab.label as keyof typeof diseaseDossierMessages) }))}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel={t("疾病专业档案视图")}
            idPrefix="disease-dossier"
          />

          <div
            className="dossier-body company-profile-body"
            id={`disease-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`disease-dossier-tab-${activeSection}`}
          >
            {activeSection === "overview" ? (
              <DiseaseOverview
                data={data}
                onOpenTypedEntity={openDiseaseEntity}
                onOpenSection={onSectionChange}
                onOpenEpidemiology={onOpenEpidemiology}
              />
            ) : null}
            {activeSection === "epidemiology" ? (
              <EpidemiologyPanel
                data={data}
                onOpen={setProvenanceSelection}
                onOpenEntity={onOpenEntity}
                onOpenTypedEntity={openDiseaseEntity}
                onOpenAll={() => onOpenEpidemiology(data.entity.id)}
              />
            ) : null}
            {activeSection === "pipeline" ? (
              <Programs
                data={data}
                onOpen={setProvenanceSelection}
                onOpenEntity={onOpenEntity}
                onOpenTypedEntity={openDiseaseEntity}
              />
            ) : null}
            {activeSection === "evidence" ? (
              <DiseaseEvidence data={data} onOpen={setProvenanceSelection} onOpenTypedEntity={openDiseaseEntity} />
            ) : null}
            {activeSection === "trials" ? (
              <Trials data={data} onOpen={setProvenanceSelection} onOpenTrial={onOpenTrial} />
            ) : null}
            {activeSection === "patents" ? (
              <Patents data={data} onOpen={setProvenanceSelection} onOpenPatent={onOpenPatent} />
            ) : null}
            {activeSection === "deals" ? (
              <Deals
                data={data}
                onOpen={setProvenanceSelection}
                onOpenEntity={onOpenEntity}
                onOpenTypedEntity={openDiseaseEntity}
                onOpenDeal={onOpenDeal}
              />
            ) : null}
            {activeSection === "regulatory" ? (
              <Regulatory data={data} onOpen={setProvenanceSelection} onOpenRegulatoryEvent={onOpenRegulatoryEvent} />
            ) : null}
            {activeSection === "news" ? (
              <News data={data} onOpen={setProvenanceSelection} onOpenNewsEvent={onOpenNewsEvent} />
            ) : null}
            {activeSection === "relationships" ? (
              <Relationships data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={openDiseaseEntity} />
            ) : null}
          </div>
        </section>
      )}
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}
