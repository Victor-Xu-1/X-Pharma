import { useQuery } from "@tanstack/react-query";
import { Pill } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { EntityNames } from "../components/EntityNames";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList } from "../components/ResearchTabList";
import { ApiError } from "../lib/api";
import { drugDossierKeys, drugProgramKeys, loadDrugDossier, loadDrugPrograms } from "../lib/contracts/drugDossier";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { useLocale } from "../lib/i18n";
import { drugDossierText as t } from "../lib/i18n/drugDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../lib/i18n/programVocabulary";
import type { Entity } from "../lib/types";
import type { DrugDossierSection } from "../lib/workspaceRouting";
import { buildDrugTabs } from "./drug/coverage";
import { DrugAssociations } from "./drug/DrugAssociations";
import { DrugClinicalEvidence } from "./drug/DrugClinicalEvidence";
import { DrugDealIntelligence } from "./drug/DrugDealIntelligence";
import { DrugDevelopmentPortfolio } from "./drug/DrugDevelopmentPortfolio";
import { DrugOverview } from "./drug/DrugOverview";
import { DrugRegulatory } from "./drug/DrugRegulatory";
import type { DrugEntityOpener } from "./drug/types";
import { Activities, News, Patents, Structures } from "./EntityDossierView";

export function DrugView({
  drug,
  activeSection,
  programOffset,
  onProgramOffsetChange,
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
  drug: Entity | null;
  activeSection: DrugDossierSection;
  programOffset: number;
  onProgramOffsetChange: (offset: number) => void;
  onSectionChange: (section: DrugDossierSection, replace?: boolean) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenDrug?: (entityId: string) => void;
  onOpenTarget?: (entityId: string) => void;
  onOpenDisease?: (entityId: string) => void;
  onOpenOrganization?: (entityId: string) => void;
  onOpenTrial: (trialId: string) => void;
  onOpenPatent: (patentId: string) => void;
  onOpenDeal: (dealId: string) => void;
  onOpenRegulatoryEvent: (eventId: string) => void;
  onOpenNewsEvent: (eventId: string) => void;
}) {
  useLocale();
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const openDrug = onOpenDrug ?? onOpenEntity;
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const openDrugEntity: DrugEntityOpener = (entityType, entityId) => {
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
  const dossier = useQuery({
    queryKey: drugDossierKeys.detail(drug?.id ?? ""),
    queryFn: ({ signal }) => loadDrugDossier(drug?.id ?? "", signal),
    enabled: Boolean(drug?.id && drug.entity_type === "drug"),
  });
  const programPage = useQuery({
    queryKey: drugProgramKeys.page(drug?.id ?? "", programOffset),
    queryFn: ({ signal }) => loadDrugPrograms(drug?.id ?? "", 100, programOffset, signal),
    enabled: Boolean(drug?.id && drug.entity_type === "drug" && activeSection === "pipeline"),
    placeholderData:
      programOffset === 0 && dossier.data
        ? {
            query_schema_version: "pharma.drug.programs.v1",
            items: dossier.data.programs,
            total:
              dossier.data.coverage.find((item) => item.domain === "programs")?.total ??
              dossier.data.summary.program_count,
            limit: 100,
            offset: 0,
            as_of: dossier.data.as_of,
            warnings: dossier.data.warnings,
          }
        : undefined,
  });

  if (!drug) return <EmptyState title={t("尚未选择药物")} detail={t("请从查询或管线结果中打开药物档案")} />;
  if (drug.entity_type !== "drug") {
    return <ErrorState message={t("该深链接不是药物实体，无法打开药物专业档案")} />;
  }
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : t("药物档案加载失败")}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={t("正在加载 {name} 药物档案", { name: drug.name })} />;
  if (dossier.data.entity.id !== drug.id || dossier.data.entity.entity_type !== "drug") {
    return <ErrorState message={t("药物档案与请求实体不一致")} retry={() => void dossier.refetch()} />;
  }

  const data = dossier.data;
  const programDenied = programPage.error instanceof ApiError && [401, 403].includes(programPage.error.status);
  const programMismatch = Boolean(
    programPage.data &&
      (programPage.data.offset !== programOffset ||
        programPage.data.items.some((program) => program.drug_entity_id !== drug.id)),
  );
  const programItems =
    programDenied || programMismatch ? [] : (programPage.data?.items ?? (programOffset === 0 ? data.programs : []));
  const programTotal =
    programPage.data?.total ??
    data.coverage.find((item) => item.domain === "programs")?.total ??
    data.summary.program_count;
  const tabs = buildDrugTabs(data, programTotal);
  return (
    <>
      <section className="drug-profile-page">
        <header className="drug-profile-header">
          <div className="drug-profile-symbol">
            <Pill size={23} />
          </div>
          <div className="drug-profile-identity">
            <h2>{data.entity.name}</h2>
            <p>{data.entity.description ?? t("暂无药物摘要")}</p>
          </div>
        </header>

        <EntityNames entity={data.entity} />
        <dl className="dossier-metrics drug-profile-metrics">
          <div>
            <dt>{t("最高阶段")}</dt>
            <dd>{phaseLabel(data.summary.highest_phase)}</dd>
          </div>
          <div>
            <dt>{t("全球 / 中国")}</dt>
            <dd>
              {phaseLabel(data.summary.highest_global_phase)} / {phaseLabel(data.summary.highest_china_phase)}
            </dd>
          </div>
          <div>
            <dt>{t("研发项目")}</dt>
            <dd>{data.summary.program_count}</dd>
          </div>
          <div>
            <dt>{t("靶点 / 适应症")}</dt>
            <dd>
              {data.summary.target_count} / {data.summary.indication_count}
            </dd>
          </div>
          <div>
            <dt>{t("研发机构")}</dt>
            <dd>{data.summary.organization_count}</dd>
          </div>
          <div>
            <dt>{t("最新状态")}</dt>
            <dd>{formatDate(data.summary.latest_status_date)}</dd>
          </div>
        </dl>

        <ResearchTabList
          tabs={tabs}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel={t("药物专业档案视图")}
          idPrefix="drug-dossier"
        />

        <div
          className="dossier-body drug-profile-body"
          id={`drug-dossier-panel-${activeSection}`}
          role="tabpanel"
          aria-labelledby={`drug-dossier-tab-${activeSection}`}
        >
          {activeSection === "overview" ? (
            <DrugOverview data={data} onOpenEntity={openDrugEntity} onOpenSection={onSectionChange} />
          ) : null}
          {activeSection === "pipeline" ? (
            <DrugDevelopmentPortfolio
              data={data}
              programs={programItems}
              totalPrograms={programTotal}
              offset={programOffset}
              pageSize={programPage.data?.limit ?? 100}
              loading={programPage.isPending}
              fetching={programPage.isFetching}
              error={programMismatch ? new Error(t("研发分页与请求药物或页位置不一致")) : programPage.error}
              onRetry={() => void programPage.refetch()}
              onPageChange={onProgramOffsetChange}
              onOpen={setProvenanceSelection}
              onOpenEntity={openDrugEntity}
            />
          ) : null}
          {activeSection === "relationships" ? (
            <DrugAssociations data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={openDrugEntity} />
          ) : null}
          {activeSection === "activities" ? <Activities data={data} onOpen={setProvenanceSelection} /> : null}
          {activeSection === "trials" ? (
            <DrugClinicalEvidence
              data={data}
              onOpen={setProvenanceSelection}
              onOpenEntity={openDrugEntity}
              onOpenTrial={onOpenTrial}
            />
          ) : null}
          {activeSection === "patents" ? (
            <Patents data={data} onOpen={setProvenanceSelection} onOpenPatent={onOpenPatent} />
          ) : null}
          {activeSection === "deals" ? (
            <DrugDealIntelligence
              data={data}
              onOpen={setProvenanceSelection}
              onOpenDeal={onOpenDeal}
              onOpenEntity={openDrugEntity}
            />
          ) : null}
          {activeSection === "regulatory" ? (
            <DrugRegulatory
              data={data}
              onOpen={setProvenanceSelection}
              onOpenEntity={openDrugEntity}
              onOpenRegulatoryEvent={onOpenRegulatoryEvent}
            />
          ) : null}
          {activeSection === "news" ? (
            <News data={data} onOpen={setProvenanceSelection} onOpenNewsEvent={onOpenNewsEvent} />
          ) : null}
          {activeSection === "structures" ? <Structures data={data} onOpen={setProvenanceSelection} /> : null}
        </div>
      </section>
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}
