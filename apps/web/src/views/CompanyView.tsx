import { useQuery } from "@tanstack/react-query";
import { Building2 } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { EntityIdentityNotice } from "../components/EntityIdentityNotice";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList } from "../components/ResearchTabList";
import { companyKeys, loadCompanyDossier } from "../lib/contracts/company";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { isProviderLabel } from "../lib/entityPresentation";
import { useLocale } from "../lib/i18n";
import { type companyDossierMessages, companyDossierText as t } from "../lib/i18n/companyDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../lib/i18n/programVocabulary";
import type { Entity } from "../lib/types";
import type { CompanyDossierSection } from "../lib/workspaceRouting";
import { CompanySourceLabelOverview } from "./CompanySourceLabelOverview";
import { CompanyOverview } from "./company/Overview";
import { tabs } from "./company/vocabulary";
import {
  CompanyTimelinePanel,
  Deals,
  type DossierEntityOpener,
  News,
  Patents,
  Programs,
  Regulatory,
  Relationships,
  Trials,
} from "./EntityDossierView";
export function CompanyView({
  company,
  activeSection,
  onSectionChange,
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
  company: Entity | null;
  activeSection: CompanyDossierSection;
  onSectionChange: (section: CompanyDossierSection, replace?: boolean) => void;
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
    queryKey: companyKeys.dossier(company?.id ?? ""),
    queryFn: ({ signal }) => loadCompanyDossier(company?.id ?? "", signal),
    enabled: Boolean(company?.id && company.entity_type === "organization"),
  });

  if (!company) return <EmptyState title={t("尚未选择公司")} detail={t("请从查询、管线或交易结果中打开公司档案")} />;
  if (company.entity_type !== "organization") {
    return <ErrorState message={t("该深链接不是机构实体，无法打开公司专业档案")} />;
  }
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : t("公司档案加载失败")}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={t("正在加载 {name} 公司档案", { name: company.name })} />;
  if (dossier.data.entity.id !== company.id || dossier.data.entity.entity_type !== "organization") {
    return <ErrorState message={t("公司档案与请求实体不一致")} retry={() => void dossier.refetch()} />;
  }

  const data = dossier.data;
  const providerLabel = isProviderLabel(data.entity);
  const openDrug = onOpenDrug ?? onOpenEntity;
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const openCompanyEntity: DossierEntityOpener = (entityType, entityId) => {
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
      <section className="company-profile-page">
        <header className="company-profile-header">
          <div className="company-profile-symbol">
            <Building2 size={23} />
          </div>
          <div className="company-profile-identity">
            {providerLabel ? <span>{t("登记申办方名称")}</span> : null}
            <h2>{data.entity.name}</h2>
            {!providerLabel ? <p>{data.entity.description ?? t("暂无公司简介")}</p> : null}
          </div>
        </header>

        <EntityIdentityNotice entity={data.entity} />

        {!providerLabel ? (
          <dl className="dossier-metrics company-profile-metrics">
            <div>
              <dt>{t("最高阶段")}</dt>
              <dd>{phaseLabel(data.summary.highest_phase)}</dd>
            </div>
            <div>
              <dt>{t("研发项目 / 药物")}</dt>
              <dd>
                {data.summary.program_count} / {data.summary.drug_count}
              </dd>
            </div>
            <div>
              <dt>{t("靶点 / 适应症")}</dt>
              <dd>
                {data.summary.target_count} / {data.summary.indication_count}
              </dd>
            </div>
            <div>
              <dt>{t("关联交易")}</dt>
              <dd>{data.summary.deal_count}</dd>
            </div>
            <div>
              <dt>{t("带日期事件")}</dt>
              <dd>{data.summary.timeline_event_count}</dd>
            </div>
            <div>
              <dt>{t("最近活动")}</dt>
              <dd>{formatDate(data.summary.latest_activity_at)}</dd>
            </div>
          </dl>
        ) : null}

        <ResearchTabList
          tabs={tabs.map((tab) => ({ ...tab, label: t(tab.label as keyof typeof companyDossierMessages) }))}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel={t("公司专业档案视图")}
          idPrefix="company-dossier"
        />

        <div
          className="dossier-body company-profile-body"
          id={`company-dossier-panel-${activeSection}`}
          role="tabpanel"
          aria-labelledby={`company-dossier-tab-${activeSection}`}
        >
          {activeSection === "overview" ? (
            providerLabel ? (
              <CompanySourceLabelOverview
                data={data}
                onOpen={setProvenanceSelection}
                onOpenTrial={onOpenTrial}
                onOpenTrials={() => onSectionChange("trials")}
              />
            ) : (
              <CompanyOverview data={data} onOpenDrug={openDrug} onOpenSection={onSectionChange} />
            )
          ) : null}
          {activeSection === "pipeline" ? (
            <Programs
              data={data}
              onOpen={setProvenanceSelection}
              onOpenEntity={onOpenEntity}
              onOpenTypedEntity={openCompanyEntity}
            />
          ) : null}
          {activeSection === "timeline" ? (
            <CompanyTimelinePanel
              timeline={data.timeline}
              loading={false}
              error={null}
              retry={() => void dossier.refetch()}
              onOpen={setProvenanceSelection}
              onOpenEntity={onOpenEntity}
              onOpenTypedEntity={openCompanyEntity}
            />
          ) : null}
          {activeSection === "deals" ? (
            <Deals
              data={data}
              onOpen={setProvenanceSelection}
              onOpenEntity={onOpenEntity}
              onOpenTypedEntity={openCompanyEntity}
              onOpenDeal={onOpenDeal}
            />
          ) : null}
          {activeSection === "relationships" ? (
            <Relationships data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={openCompanyEntity} />
          ) : null}
          {activeSection === "trials" ? (
            <Trials data={data} onOpen={setProvenanceSelection} onOpenTrial={onOpenTrial} />
          ) : null}
          {activeSection === "patents" ? (
            <Patents data={data} onOpen={setProvenanceSelection} onOpenPatent={onOpenPatent} />
          ) : null}
          {activeSection === "regulatory" ? (
            <Regulatory data={data} onOpen={setProvenanceSelection} onOpenRegulatoryEvent={onOpenRegulatoryEvent} />
          ) : null}
          {activeSection === "news" ? (
            <News data={data} onOpen={setProvenanceSelection} onOpenNewsEvent={onOpenNewsEvent} />
          ) : null}
        </div>
      </section>
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}
