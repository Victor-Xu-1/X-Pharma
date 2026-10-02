import { useQuery } from "@tanstack/react-query";
import { Dna } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner } from "../components/common";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
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
import { organismLabel, targetClassLabel, targetDisplayIdentity } from "../lib/targetDisplay";
import type { Entity } from "../lib/types";
import type { TargetDossierSection } from "../lib/workspaceRouting";
import { TargetPipeline } from "./target/pipeline/TargetPipeline";
import { Relationships, TargetEvidenceTable } from "./target/TargetEvidencePanels";
import { Activities, Structures, TargetSarPanel } from "./target/TargetMolecularData";
import { Overview } from "./target/TargetOverview";
import { Deals, NewsEvents, Patents, RegulatoryEvents, Trials } from "./target/TargetRelatedRecords";
import type { TargetEntityOpener } from "./target/types";

const tabs: Array<ResearchTabOption<TargetDossierSection>> = [
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
    enabled: Boolean(target),
  });
  if (!target) return <EmptyState title="尚未选择靶点" detail="请从情报检索结果中打开一个靶点" />;
  if (dossier.error) {
    const message = dossier.error instanceof Error ? dossier.error.message : "靶点档案加载失败";
    return <ErrorState message={message} retry={() => void dossier.refetch()} />;
  }
  if (!dossier.data) return <Spinner label={`正在加载 ${target.name} 全景档案`} />;
  const data = dossier.data;
  const displayIdentity = targetDisplayIdentity({
    name: data.profile.entity.name,
    description: data.profile.entity.description,
    geneSymbol: data.profile.gene_symbol,
  });

  return (
    <>
      <section className="target-dossier">
        <div className="target-title-row">
          <div>
            <div className="target-symbol">
              <Dna size={25} />
            </div>
            <div>
              <h2>{displayIdentity.primaryName}</h2>
              {displayIdentity.fullName ? <p>{displayIdentity.fullName}</p> : null}
              <p>
                {targetClassLabel(data.profile.target_class)} · {organismLabel(data.profile.organism)}
              </p>
            </div>
          </div>
          {data.profile.profile_id ? (
            <ProvenanceButton
              selection={{
                resourceType: "target_profile",
                resourceId: data.profile.profile_id,
                label: `${data.profile.entity.name} 靶点档案`,
              }}
              onOpen={setProvenanceSelection}
            />
          ) : null}
        </div>
        <dl className="dossier-metrics">
          <div>
            <dt>基因符号</dt>
            <dd>{data.profile.gene_symbol ?? "--"}</dd>
          </div>
          <div>
            <dt>UniProt</dt>
            <dd>{data.profile.uniprot_accession ?? "--"}</dd>
          </div>
          <div>
            <dt>活性记录</dt>
            <dd>{data.profile.activity_count}</dd>
          </div>
          <div>
            <dt>转化证据</dt>
            <dd>{data.profile.target_evidence_count ?? data.target_evidence.length}</dd>
          </div>
          <div>
            <dt>竞品项目</dt>
            <dd>{data.profile.program_count}</dd>
          </div>
          <div>
            <dt>数据截至</dt>
            <dd>{formatDate(data.profile.as_of)}</dd>
          </div>
        </dl>
        <ResearchTabList
          tabs={tabs}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel="靶点档案视图"
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
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}
