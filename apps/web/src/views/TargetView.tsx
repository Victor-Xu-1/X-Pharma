import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { EmptyState, ErrorState, Spinner } from "../components/common";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import type {
  PipelineAnalysisDimension,
  PipelineAnalysisLimit,
  PipelineAnalysisStageScope,
  PipelineAnalysisView,
  PipelineSearchFilters,
  PipelineTargetAggregation,
} from "../lib/contracts/pipeline";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { loadTargetDossier, targetKeys } from "../lib/contracts/target";
import { useMessages } from "../lib/i18n";
import { targetDossierMessages } from "../lib/i18n/targetDossier";
import type { Entity } from "../lib/types";
import type { TargetDossierSection } from "../lib/workspaceRouting";
import { TargetPipeline } from "./target/pipeline/TargetPipeline";
import { TargetDossierHeader } from "./target/TargetDossierHeader";
import { Relationships, TargetEvidenceTable } from "./target/TargetEvidencePanels";
import { Activities, Structures, TargetSarPanel } from "./target/TargetMolecularData";
import { Overview } from "./target/TargetOverview";
import { Deals, NewsEvents, Patents, RegulatoryEvents, Trials } from "./target/TargetRelatedRecords";
import type { TargetEntityOpener } from "./target/types";

const tabLabels: Array<ResearchTabOption<TargetDossierSection> & { label: keyof typeof targetDossierMessages }> = [
  { key: "overview", label: "概览" },
  { key: "relationships", label: "关系网络" },
  { key: "evidence", label: "转化证据" },
  { key: "activities", label: "活性数据" },
  { key: "sar", label: "SAR 对比" },
  { key: "pipeline", label: "竞品管线" },
  { key: "trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易" },
  { key: "regulatory", label: "监管动态" },
  { key: "news", label: "新闻与会议" },
  { key: "structures", label: "结构" },
];

export function TargetView({
  target,
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
  onOpenEvidence,
  onOpenComparison,
  initialPipelineFilters,
  onPipelineSearchChange,
  onPipelineLandscapeFilterApply,
  initialPipelineDisplayMode,
  onPipelineDisplayModeChange,
  initialPipelineAnalysis,
  onPipelineAnalysisChange,
}: {
  target: Entity | null;
  activeSection: TargetDossierSection;
  onSectionChange: (section: TargetDossierSection) => void;
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
  onOpenEvidence?: (query: string) => void;
  onOpenComparison?: (comparisonSetId: string, entityIds: string[]) => void;
  initialPipelineFilters?: PipelineSearchFilters;
  onPipelineSearchChange?: (filters: PipelineSearchFilters) => void;
  onPipelineLandscapeFilterApply?: (
    filters: PipelineSearchFilters,
    displayMode: "drug" | "program" | "landscape",
  ) => void;
  initialPipelineDisplayMode?: "drug" | "program" | "landscape";
  onPipelineDisplayModeChange?: (displayMode: "drug" | "program" | "landscape") => void;
  initialPipelineAnalysis?: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  };
  onPipelineAnalysisChange?: (analysis: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
}) {
  const text = useMessages(targetDossierMessages);
  const tabs = tabLabels.map((tab) => ({ ...tab, label: text(tab.label) }));
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const openDrug = onOpenDrug ?? onOpenEntity;
  const openTarget = onOpenTarget ?? onOpenEntity;
  const openDisease = onOpenDisease ?? onOpenEntity;
  const openOrganization = onOpenOrganization ?? onOpenEntity;
  const openTargetEntity: TargetEntityOpener = (entityType, entityId) => {
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
    queryKey: targetKeys.dossier(target?.id ?? ""),
    queryFn: ({ signal }) => loadTargetDossier(target?.id ?? "", signal),
    enabled: Boolean(target && target.entity_type === "target"),
  });
  if (!target) return <EmptyState title={text("尚未选择靶点")} detail={text("请从情报检索结果中打开一个靶点")} />;
  if (target.entity_type !== "target") {
    return <ErrorState message={text("该深链接不是靶点实体，无法打开靶点档案")} />;
  }
  if (dossier.error) {
    const message = dossier.error instanceof Error ? dossier.error.message : text("靶点档案加载失败");
    return <ErrorState message={message} retry={() => void dossier.refetch()} />;
  }
  if (!dossier.data) return <Spinner label={text("正在加载 {name} 全景档案", { name: target.name })} />;
  const data = dossier.data;
  if (
    data.entity.id !== target.id ||
    data.entity.entity_type !== "target" ||
    data.profile.entity.id !== target.id ||
    data.profile.entity.entity_type !== "target"
  ) {
    return <ErrorState message={text("靶点档案与请求实体不一致")} retry={() => void dossier.refetch()} />;
  }

  return (
    <>
      <section className="target-dossier">
        <TargetDossierHeader
          key={target.id}
          profile={data.profile}
          returnedEvidenceCount={data.target_evidence.length}
          onOpenProvenance={setProvenanceSelection}
        />
        <ResearchTabList
          tabs={tabs}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel={text("靶点档案视图")}
          idPrefix="target-dossier"
        />
        <div
          className="dossier-body"
          id={`target-dossier-panel-${activeSection}`}
          role="tabpanel"
          aria-labelledby={`target-dossier-tab-${activeSection}`}
        >
          {activeSection === "overview" ? (
            <Overview data={data} onOpenSection={onSectionChange} onOpenEvidence={onOpenEvidence} />
          ) : null}
          {activeSection === "relationships" ? (
            <Relationships items={data.relationships} onOpenEntity={openTargetEntity} />
          ) : null}
          {activeSection === "evidence" ? (
            <TargetEvidenceTable
              items={data.target_evidence}
              onOpen={setProvenanceSelection}
              onOpenEntity={openTargetEntity}
            />
          ) : null}
          {activeSection === "activities" ? (
            <Activities items={data.activities} onOpen={setProvenanceSelection} onOpenEntity={onOpenEntity} />
          ) : null}
          {activeSection === "sar" ? (
            <TargetSarPanel targetId={target.id} onOpen={setProvenanceSelection} onOpenEntity={onOpenEntity} />
          ) : null}
          {activeSection === "pipeline" ? (
            <TargetPipeline
              key={target.id}
              targetId={target.id}
              targetName={target.name}
              fallbackItems={data.programs}
              initialFilters={initialPipelineFilters}
              onFiltersChange={onPipelineSearchChange}
              onLandscapeFilterApply={onPipelineLandscapeFilterApply}
              initialDisplayMode={initialPipelineDisplayMode}
              onDisplayModeChange={onPipelineDisplayModeChange}
              initialAnalysis={initialPipelineAnalysis}
              onAnalysisChange={onPipelineAnalysisChange}
              onOpen={setProvenanceSelection}
              onOpenEntity={openTargetEntity}
              onOpenComparison={onOpenComparison}
            />
          ) : null}
          {activeSection === "trials" ? (
            <Trials items={data.clinical_trials} onOpen={setProvenanceSelection} onOpenTrial={onOpenTrial} />
          ) : null}
          {activeSection === "patents" ? (
            <Patents items={data.patents} onOpen={setProvenanceSelection} onOpenPatent={onOpenPatent} />
          ) : null}
          {activeSection === "deals" ? (
            <Deals items={data.deals} onOpen={setProvenanceSelection} onOpenDeal={onOpenDeal} />
          ) : null}
          {activeSection === "regulatory" ? (
            <RegulatoryEvents
              items={data.regulatory_events}
              onOpen={setProvenanceSelection}
              onOpenRegulatoryEvent={onOpenRegulatoryEvent}
            />
          ) : null}
          {activeSection === "news" ? (
            <NewsEvents items={data.news_events} onOpen={setProvenanceSelection} onOpenNewsEvent={onOpenNewsEvent} />
          ) : null}
          {activeSection === "structures" ? (
            <Structures items={data.structures} onOpen={setProvenanceSelection} />
          ) : null}
        </div>
      </section>
      {provenanceSelection ? (
        <RecordProvenanceDrawer
          selection={
            provenanceSelection.resourceType === "target_profile"
              ? { ...provenanceSelection, label: text("{name} 靶点档案", { name: data.profile.entity.name }) }
              : provenanceSelection
          }
          onClose={() => setProvenanceSelection(null)}
        />
      ) : null}
    </>
  );
}
