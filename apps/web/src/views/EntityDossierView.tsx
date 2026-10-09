import { useQuery } from "@tanstack/react-query";
import { Network } from "lucide-react";
import { useEffect, useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { DossierActivityTable as Activities } from "../components/DossierActivityTable";
import { EntityNames } from "../components/EntityNames";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList } from "../components/ResearchTabList";
import { companyKeys, loadCompanyTimeline } from "../lib/contracts/company";
import { entityDossierKeys, loadEntityDossier } from "../lib/contracts/entityDossier";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { entityTypeLabel } from "../lib/entityPresentation";
import { useLocale } from "../lib/i18n";
import { type dossierRecordMessages, dossierRecordText as t } from "../lib/i18n/dossierRecords";
import type { Entity } from "../lib/types";
import type { EntityDossierSection } from "../lib/workspaceRouting";
import { CompanyIntelligence } from "./dossier/CompanyIntelligence";
import { Deals } from "./dossier/Deals";
import { News } from "./dossier/News";
import { DossierOverview } from "./dossier/Overview";
import { Patents } from "./dossier/Patents";
import { Programs } from "./dossier/Programs";
import { Regulatory } from "./dossier/Regulatory";
import { Relationships } from "./dossier/Relationships";
import { Structures } from "./dossier/Structures";
import { Trials } from "./dossier/Trials";
import type { DossierEntityOpener } from "./dossier/types";
import { tabs } from "./dossier/vocabulary";

export type { DossierEntityOpener } from "./dossier/types";
export { Activities, News, Patents, Regulatory, Relationships, Structures };

export function EntityDossierView({
  entity,
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
  entity: Entity | null;
  activeSection: EntityDossierSection;
  onSectionChange: (section: EntityDossierSection, replace?: boolean) => void;
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
    queryKey: entityDossierKeys.detail(entity?.id ?? ""),
    queryFn: ({ signal }) => loadEntityDossier(entity?.id ?? "", signal),
    enabled: Boolean(entity),
  });
  const companyTimeline = useQuery({
    queryKey: companyKeys.timeline(entity?.id ?? "", 0),
    queryFn: ({ signal }) => loadCompanyTimeline(entity?.id ?? "", 0, signal),
    enabled: entity?.entity_type === "organization",
  });
  const invalidCompanySection = Boolean(
    dossier.data && activeSection === "company_intelligence" && dossier.data.entity.entity_type !== "organization",
  );

  useEffect(() => {
    if (invalidCompanySection) onSectionChange("overview", true);
  }, [invalidCompanySection, onSectionChange]);

  if (!entity) return <EmptyState title={t("尚未选择领域实体")} detail={t("请从基础查询结果中打开一个实体")} />;
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : t("领域档案加载失败")}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={t("正在加载 {name} 领域档案", { name: entity.name })} />;

  const data = dossier.data;
  const translatedTabs = tabs.map((tab) => ({ ...tab, label: t(tab.label as keyof typeof dossierRecordMessages) }));
  const visibleTabs =
    data.entity.entity_type === "organization"
      ? translatedTabs
      : translatedTabs.filter((tab) => tab.key !== "company_intelligence");
  const effectiveSection = invalidCompanySection ? "overview" : activeSection;
  const openTypedEntity: DossierEntityOpener = (entityType, entityId) => {
    switch (entityType) {
      case "drug":
        (onOpenDrug ?? onOpenEntity)(entityId);
        return;
      case "target":
        (onOpenTarget ?? onOpenEntity)(entityId);
        return;
      case "disease":
        (onOpenDisease ?? onOpenEntity)(entityId);
        return;
      case "organization":
        (onOpenOrganization ?? onOpenEntity)(entityId);
        return;
      default:
        onOpenEntity(entityId);
    }
  };
  const totalRecords = data.coverage.reduce((sum, item) => sum + item.total, 0);
  const availableDomains = data.coverage.filter((item) => item.total > 0).length;

  return (
    <>
      <section className="entity-dossier-page">
        <header className="entity-dossier-title">
          <div className="entity-dossier-symbol">
            <Network size={23} />
          </div>
          <div>
            <span>{entityTypeLabel(data.entity)}</span>
            <h2>{data.entity.name}</h2>
            <p>{data.entity.description ?? t("暂无实体摘要")}</p>
          </div>
        </header>
        <EntityNames entity={data.entity} />

        <dl className="dossier-metrics entity-dossier-metrics">
          <div>
            <dt>{t("关联记录")}</dt>
            <dd>{totalRecords}</dd>
          </div>
          <div>
            <dt>{t("有数据领域")}</dt>
            <dd>
              {availableDomains} / {data.coverage.length}
            </dd>
          </div>
          <div>
            <dt>{t("直接关系")}</dt>
            <dd>{data.relationships.length}</dd>
          </div>
          <div>
            <dt>{t("查询时间")}</dt>
            <dd title={t("本次档案查询时间不代表所有来源的最后更新时间")}>{formatDate(data.as_of, true)}</dd>
          </div>
        </dl>

        <ResearchTabList
          tabs={visibleTabs}
          activeTab={effectiveSection}
          onChange={onSectionChange}
          ariaLabel={t("领域档案视图")}
          idPrefix="entity-dossier"
        />

        <div
          className="dossier-body"
          id={`entity-dossier-panel-${effectiveSection}`}
          role="tabpanel"
          aria-labelledby={`entity-dossier-tab-${effectiveSection}`}
        >
          {effectiveSection === "overview" ? <DossierOverview data={data} onOpenSection={onSectionChange} /> : null}
          {effectiveSection === "company_intelligence" ? (
            <CompanyIntelligence
              data={data}
              timeline={companyTimeline.data}
              loading={companyTimeline.isFetching}
              error={companyTimeline.error}
              retry={() => void companyTimeline.refetch()}
              onOpen={setProvenanceSelection}
              onOpenEntity={onOpenEntity}
              onOpenTypedEntity={openTypedEntity}
            />
          ) : null}
          {effectiveSection === "relationships" ? (
            <Relationships data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={openTypedEntity} />
          ) : null}
          {effectiveSection === "programs" ? (
            <Programs
              data={data}
              onOpen={setProvenanceSelection}
              onOpenEntity={onOpenEntity}
              onOpenTypedEntity={openTypedEntity}
            />
          ) : null}
          {effectiveSection === "activities" ? <Activities data={data} onOpen={setProvenanceSelection} /> : null}
          {effectiveSection === "clinical_trials" ? (
            <Trials data={data} onOpen={setProvenanceSelection} onOpenTrial={onOpenTrial} />
          ) : null}
          {effectiveSection === "patents" ? (
            <Patents data={data} onOpen={setProvenanceSelection} onOpenPatent={onOpenPatent} />
          ) : null}
          {effectiveSection === "deals" ? (
            <Deals
              data={data}
              onOpen={setProvenanceSelection}
              onOpenEntity={onOpenEntity}
              onOpenTypedEntity={openTypedEntity}
              onOpenDeal={onOpenDeal}
            />
          ) : null}
          {effectiveSection === "regulatory_events" ? (
            <Regulatory data={data} onOpen={setProvenanceSelection} onOpenRegulatoryEvent={onOpenRegulatoryEvent} />
          ) : null}
          {effectiveSection === "news_events" ? (
            <News data={data} onOpen={setProvenanceSelection} onOpenNewsEvent={onOpenNewsEvent} />
          ) : null}
          {effectiveSection === "structures" ? <Structures data={data} onOpen={setProvenanceSelection} /> : null}
        </div>
      </section>
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}

export { CompanyTimelinePanel } from "./dossier/CompanyTimelinePanel";
export { Deals } from "./dossier/Deals";
export { Programs } from "./dossier/Programs";
export { Trials } from "./dossier/Trials";
