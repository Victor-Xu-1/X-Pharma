import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Columns3,
  Dna,
  FileCheck2,
  FileText,
  Newspaper,
  RotateCcw,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { AddToComparisonControl } from "../components/AddToComparisonControl";
import { AppliedFiltersBar } from "../components/AppliedFiltersBar";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge, stringifyParty } from "../components/common";
import { EntityFilterSelect } from "../components/EntityFilterSelect";
import { FacetMultiSelect } from "../components/FacetMultiSelect";
import { MoleculeDepiction } from "../components/MoleculeDepiction";
import { PatentTimeline } from "../components/PatentTimeline";
import { PipelineLandscape, type PipelineLandscapeFilterField } from "../components/PipelineLandscape";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import {
  emptyPipelineSearchFilters,
  hasPipelineSearchFilter,
  type PipelineAnalysisDimension,
  type PipelineAnalysisLimit,
  type PipelineAnalysisStageScope,
  type PipelineAnalysisView,
  type PipelineResultGrain,
  type PipelineSearchFilters,
  type PipelineSortField,
  type PipelineTargetAggregation,
  pipelineKeys,
  type SortDirection,
  searchPipelines,
} from "../lib/contracts/pipeline";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import {
  type Bioactivity,
  type ClinicalTrial,
  type CompetitiveProgram,
  type CompoundStructure,
  type Deal,
  loadTargetDossier,
  loadTargetSar,
  type PatentFamily,
  type RegulatoryEvent,
  type SarActivity,
  type SarFilters,
  type TargetDossier,
  type TargetEvidence,
  type TargetNewsEvent,
  type TargetRelationship,
  targetKeys,
} from "../lib/contracts/target";
import type { AppliedFilterRead, EntityType, PipelineLandscapeRead } from "../lib/generated";
import { pipelineResultEvaluationLabels } from "../lib/pipelineSignals";
import { isPublicProgramTag, programModalityLabel, programTagLabel, publicProgramTags } from "../lib/programDisplay";
import { organismLabel, targetClassLabel, targetDisplayIdentity } from "../lib/targetDisplay";
import { clinicalTrialPhaseLabel, clinicalTrialStatusLabel } from "../lib/trialDisplay";
import type { Entity } from "../lib/types";
import type { TargetDossierSection } from "../lib/workspaceRouting";

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

type TargetEntityOpener = (entityType: EntityType, entityId: string) => void;

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

function Overview({
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

function Relationships({ items, onOpenEntity }: { items: TargetRelationship[]; onOpenEntity: TargetEntityOpener }) {
  if (!items.length) return <EmptyState title="暂无关联实体" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点实体关系">
      <table aria-label="靶点实体关系">
        <thead>
          <tr>
            <th>方向</th>
            <th>关系</th>
            <th>关联实体</th>
            <th>类型</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.direction === "outgoing" ? "指向" : "来自"}</td>
              <td className="mono-cell">{item.predicate}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenEntity(item.related_entity.entity_type, item.related_entity.id)}
                >
                  {item.related_entity.name}
                </button>
              </td>
              <td>{item.related_entity.entity_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

function TargetEvidenceTable({
  items,
  onOpen,
  onOpenEntity,
}: {
  items: TargetEvidence[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: TargetEntityOpener;
}) {
  const [evidenceType, setEvidenceType] = useState("");
  const [direction, setDirection] = useState("");
  const filtered = items.filter(
    (item) => (!evidenceType || item.evidence_type === evidenceType) && (!direction || item.direction === direction),
  );
  if (!items.length) {
    return (
      <EmptyState
        title="暂无遗传、表达或转化证据"
        detail="当前可用来源和更新时间范围内未观察到记录，不代表该靶点不存在相关证据"
      />
    );
  }
  return (
    <div className="target-evidence-panel">
      <fieldset className="target-evidence-filters">
        <legend className="sr-only">转化证据筛选</legend>
        <label>
          证据类型
          <select value={evidenceType} onChange={(event) => setEvidenceType(event.target.value)}>
            <option value="">全部</option>
            <option value="genetic_association">遗传关联</option>
            <option value="expression">表达</option>
            <option value="functional">功能验证</option>
            <option value="translational">转化研究</option>
            <option value="biomarker">生物标志物</option>
            <option value="safety">安全性</option>
          </select>
        </label>
        <label>
          证据方向
          <select value={direction} onChange={(event) => setDirection(event.target.value)}>
            <option value="">全部</option>
            <option value="supports">支持</option>
            <option value="opposes">反对</option>
            <option value="neutral">中性</option>
            <option value="unknown">未知</option>
          </select>
        </label>
        <span>
          {filtered.length} / {items.length} 条
        </span>
      </fieldset>
      {!filtered.length ? (
        <EmptyState title="当前筛选条件下无匹配证据" />
      ) : (
        <ScrollableTableRegion ariaLabel="靶点转化证据">
          <table aria-label="靶点转化证据">
            <thead>
              <tr>
                <th>类型 / 方向</th>
                <th>疾病</th>
                <th>研究与人群</th>
                <th>组织 / 变异</th>
                <th>效应</th>
                <th>证据摘要</th>
                <th>观察时间</th>
                <th aria-label="原始证据" />
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr key={item.id}>
                  <td>
                    <strong>{targetEvidenceTypeLabel(item.evidence_type)}</strong>
                    <small className="table-secondary">{targetEvidenceDirectionLabel(item.direction)}</small>
                  </td>
                  <td>
                    {item.disease_entity_id ? (
                      <button
                        className="table-link-button"
                        type="button"
                        onClick={() => onOpenEntity("disease", item.disease_entity_id ?? "")}
                      >
                        {item.disease_name ?? item.disease_entity_id}
                      </button>
                    ) : (
                      "--"
                    )}
                  </td>
                  <td>
                    {item.study_name ?? "--"}
                    <small className="table-secondary">{item.population ?? "人群未记录"}</small>
                  </td>
                  <td>
                    {item.tissue ?? "--"}
                    <small className="table-secondary">{item.variant ?? "变异未记录"}</small>
                  </td>
                  <td>
                    {item.effect_size ?? "--"} {item.effect_unit ?? ""}
                    <small className="table-secondary">
                      p={item.p_value ?? "--"} · n={item.sample_size ?? "--"}
                    </small>
                  </td>
                  <td>{item.summary}</td>
                  <td>{formatDate(item.observed_at)}</td>
                  <td>
                    <ProvenanceButton
                      selection={{ resourceType: "target_evidence", resourceId: item.id, label: item.summary }}
                      onOpen={onOpen}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      )}
    </div>
  );
}

function targetEvidenceTypeLabel(value: TargetEvidence["evidence_type"]): string {
  return {
    genetic_association: "遗传关联",
    expression: "表达",
    functional: "功能验证",
    translational: "转化研究",
    biomarker: "生物标志物",
    safety: "安全性",
  }[value];
}

function targetEvidenceDirectionLabel(value: TargetEvidence["direction"]): string {
  return { supports: "支持靶点假设", opposes: "反对靶点假设", neutral: "中性", unknown: "方向未知" }[value];
}

function TargetSarPanel({
  targetId,
  onOpen,
  onOpenEntity,
}: {
  targetId: string;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
}) {
  const [filters, setFilters] = useState<SarFilters>({
    standardType: "",
    assayType: "",
    assayFormat: "",
    organism: "",
    cellLine: "",
    offset: 0,
  });
  const sar = useQuery({
    queryKey: targetKeys.sar(targetId, filters),
    queryFn: ({ signal }) => loadTargetSar(targetId, filters, signal),
  });
  function setFilter(field: keyof Omit<SarFilters, "offset">, value: string) {
    setFilters((current) => ({ ...current, [field]: value, offset: 0 }));
  }
  if (sar.isPending) return <Spinner label="正在计算可比 SAR 分组" />;
  if (sar.error) {
    return (
      <ErrorState
        message={sar.error instanceof Error ? sar.error.message : "SAR 对比加载失败"}
        retry={() => void sar.refetch()}
      />
    );
  }
  const result = sar.data;
  return (
    <div className="sar-panel">
      <fieldset className="sar-filters">
        <legend className="sr-only">SAR 对比筛选</legend>
        <SarFacetSelect
          label="指标"
          value={filters.standardType}
          values={result.facets?.standard_type}
          onChange={(value) => setFilter("standardType", value)}
        />
        <SarFacetSelect
          label="Assay 类型"
          value={filters.assayType}
          values={result.facets?.assay_type}
          onChange={(value) => setFilter("assayType", value)}
        />
        <SarFacetSelect
          label="Assay 格式"
          value={filters.assayFormat}
          values={result.facets?.assay_format}
          onChange={(value) => setFilter("assayFormat", value)}
        />
        <SarFacetSelect
          label="物种"
          value={filters.organism}
          values={result.facets?.organism}
          onChange={(value) => setFilter("organism", value)}
        />
        <SarFacetSelect
          label="细胞系"
          value={filters.cellLine}
          values={result.facets?.cell_line}
          onChange={(value) => setFilter("cellLine", value)}
        />
        <span>{result.total} 条记录</span>
      </fieldset>
      {(result.warnings ?? []).map((warning) => (
        <p className="inline-alert" key={warning}>
          {warning}
        </p>
      ))}
      {result.items.length ? (
        <>
          <ScrollableTableRegion ariaLabel="SAR 活性对比结果" className="sar-table-frame">
            <table aria-label="SAR 活性对比结果">
              <thead>
                <tr>
                  <th>结构</th>
                  <th>化合物</th>
                  <th>标准活性</th>
                  <th>pChEMBL</th>
                  <th>组内排名</th>
                  <th>ΔpChEMBL</th>
                  <th>Assay 上下文</th>
                  <th>可比性</th>
                  <th aria-label="原始证据" />
                </tr>
              </thead>
              <tbody>
                {result.items.map((item) => (
                  <SarActivityRow item={item} onOpen={onOpen} onOpenEntity={onOpenEntity} key={item.id} />
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          {result.total > result.limit ? (
            <nav className="sar-pagination" aria-label="SAR 对比分页">
              <button
                className="icon-button"
                type="button"
                title="上一页"
                aria-label="SAR 上一页"
                disabled={filters.offset === 0}
                onClick={() => setFilters((current) => ({ ...current, offset: Math.max(0, current.offset - 50) }))}
              >
                <ChevronLeft size={17} />
              </button>
              <span>
                {filters.offset + 1}-{Math.min(filters.offset + result.items.length, result.total)} / {result.total}
              </span>
              <button
                className="icon-button"
                type="button"
                title="下一页"
                aria-label="SAR 下一页"
                disabled={filters.offset + result.items.length >= result.total}
                onClick={() => setFilters((current) => ({ ...current, offset: current.offset + 50 }))}
              >
                <ChevronRight size={17} />
              </button>
            </nav>
          ) : null}
        </>
      ) : (
        <EmptyState title="当前筛选条件下暂无 SAR 记录" detail="调整指标或 Assay 上下文后重试" />
      )}
    </div>
  );
}

function SarFacetSelect({
  label,
  value,
  values,
  onChange,
}: {
  label: string;
  value: string;
  values: Record<string, number> | undefined;
  onChange: (value: string) => void;
}) {
  return (
    <label>
      {label}
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">全部</option>
        {Object.entries(values ?? {}).map(([item, count]) => (
          <option value={item} key={item}>
            {item} ({count})
          </option>
        ))}
      </select>
    </label>
  );
}

function SarActivityRow({
  item,
  onOpen,
  onOpenEntity,
}: {
  item: SarActivity;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
}) {
  return (
    <tr>
      <td>
        <div className="sar-structure">
          {item.canonical_smiles ? (
            <MoleculeDepiction smiles={item.canonical_smiles} name={item.compound_name} />
          ) : (
            <span>结构未收录</span>
          )}
        </div>
      </td>
      <td>
        <button className="table-link-button" type="button" onClick={() => onOpenEntity(item.compound_entity_id)}>
          {item.compound_name}
        </button>
        <small className="table-secondary mono-cell">{item.standard_inchi_key ?? item.compound_entity_id}</small>
      </td>
      <td>
        {item.standard_type ?? "活性指标未记录"}
        <small className="table-secondary">
          {item.standard_relation ?? ""} {item.standard_value ?? "--"} {item.standard_units ?? ""}
        </small>
      </td>
      <td>{item.pchembl_value?.toFixed(2) ?? "--"}</td>
      <td>{item.potency_rank ?? "--"}</td>
      <td>{item.delta_pchembl === null || item.delta_pchembl === undefined ? "--" : item.delta_pchembl.toFixed(2)}</td>
      <td>
        {item.assay_type ?? "类型未记录"} · {item.assay_format ?? "格式未记录"}
        <small className="table-secondary">
          {item.organism ?? "物种未记录"} · {item.cell_line ?? "无细胞系"}
        </small>
      </td>
      <td>
        <StatusBadge
          value={item.comparable ? "comparable" : "not_comparable"}
          label={item.comparable ? "可组内比较" : "不可直接比较"}
        />
        {!item.comparable ? (
          <small className="table-secondary">{(item.comparability_reasons ?? []).map(sarReasonLabel).join("；")}</small>
        ) : null}
      </td>
      <td>
        <ProvenanceButton
          selection={{ resourceType: "activity_measurement", resourceId: item.id, label: `${item.compound_name} SAR` }}
          onOpen={onOpen}
        />
      </td>
    </tr>
  );
}

function sarReasonLabel(reason: string): string {
  return (
    {
      standard_type_missing: "缺少标准指标",
      pchembl_missing: "缺少 pChEMBL",
      censored_or_approximate_relation: "上下限或近似值",
      assay_type_missing: "缺少 Assay 类型",
      assay_format_missing: "缺少 Assay 格式",
    }[reason] ?? reason
  );
}

function Activities({
  items,
  onOpen,
  onOpenEntity,
}: {
  items: Bioactivity[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
}) {
  if (!items.length) {
    return <EmptyState title="暂无活性数据" detail="当前可见来源和更新时间范围内没有可展示的活性记录" />;
  }
  return (
    <ScrollableTableRegion ariaLabel="靶点活性数据">
      <table aria-label="靶点活性数据">
        <thead>
          <tr>
            <th>化合物实体</th>
            <th>实验类型</th>
            <th>标准值</th>
            <th>pChEMBL</th>
            <th>Assay</th>
            <th>来源</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <button
                  className="table-link-button mono-cell"
                  type="button"
                  onClick={() => onOpenEntity(item.compound_entity_id)}
                >
                  {item.compound_entity_id}
                </button>
              </td>
              <td>{item.standard_type ?? item.reported_type}</td>
              <td>
                {item.standard_relation ?? item.reported_relation} {item.standard_value ?? item.reported_value}{" "}
                {item.standard_units ?? item.reported_units}
              </td>
              <td>{item.pchembl_value ?? "--"}</td>
              <td className="mono-cell">{item.assay_id}</td>
              <td>{item.source_system}</td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "activity_measurement", resourceId: item.id, label: "活性记录" }}
                  onOpen={onOpen}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

const targetDrugColumnOptions = [
  { key: "organizations", label: "研发机构" },
  { key: "targets", label: "靶点组合" },
  { key: "mechanism", label: "类型 / 机制" },
  { key: "indications", label: "适应症与阶段" },
  { key: "global_phase", label: "全球最高阶段" },
  { key: "china_phase", label: "中国最高阶段" },
  { key: "status", label: "项目状态" },
  { key: "clinical", label: "临床结果" },
  { key: "innovation", label: "创新类型" },
  { key: "updated", label: "最近更新" },
] as const;

type TargetDrugColumnKey = (typeof targetDrugColumnOptions)[number]["key"];

function defaultTargetDrugColumns(): Set<TargetDrugColumnKey> {
  return new Set(targetDrugColumnOptions.map((column) => column.key));
}

function countAdvancedPipelineFilters(filters: PipelineSearchFilters): number {
  return [
    filters.innovationTypes.length,
    filters.drugCategories.length,
    filters.organizationRole,
    filters.organizationEntityId,
    filters.organizationType,
    filters.organizationCountryRegion,
    filters.globalPhase,
    filters.chinaPhase,
    filters.developmentRightsRegion,
    filters.commercializationRightsRegion,
    filters.programTags.length,
    filters.milestoneType,
    filters.globalPhaseStartedFrom,
    filters.globalPhaseStartedTo,
    filters.chinaPhaseStartedFrom,
    filters.chinaPhaseStartedTo,
    filters.statusDateFrom,
    filters.statusDateTo,
    filters.milestoneFrom,
    filters.milestoneTo,
    filters.clinicalResultEvaluation,
    filters.dealCurrency,
    filters.dealTotalPotentialAmountMin,
    filters.dealTotalPotentialAmountMax,
    filters.targetCombinationKey,
    filters.diseaseEntityId,
  ].filter(Boolean).length;
}

const targetPipelineAppliedFilterLabels: Record<string, string> = {
  query: "药物或机构",
  modality: "药物类型",
  therapeutic_area: "适应症领域",
  innovation_type: "创新类型",
  drug_category: "药品类别",
  program_status: "项目状态",
  organization_role: "机构角色",
  organization_entity: "研发机构",
  organization_type: "机构标签",
  organization_country_region: "机构所在地区",
  target_combination_key: "靶点组合",
  disease_entity: "适应症",
  phase: "最高阶段",
  geography: "地区",
  global_phase: "全球最高阶段",
  china_phase: "中国最高阶段",
  development_rights_region: "研发权益地区",
  commercialization_rights_region: "商业化权益地区",
  program_tag: "项目标签",
  milestone_type: "里程碑类型",
  clinical_result: "临床结果",
  clinical_result_evaluation: "临床结果评价",
  deal: "交易信号",
  deal_currency: "交易币种",
  deal_total_potential_amount: "潜在交易总额",
  global_phase_started_at: "全球阶段开始日期",
  china_phase_started_at: "中国阶段开始日期",
  status_date: "状态更新日期",
  milestone_date: "里程碑日期",
};

function landscapeFilterLabel(
  landscape: PipelineLandscapeRead | undefined,
  field: "target_combinations" | "diseases",
  key: string,
  fallback: string,
) {
  return landscape?.[field]?.find((bucket) => bucket.key === key)?.label ?? fallback;
}

function targetPipelineAppliedFilters(
  filters: PipelineSearchFilters,
  landscape?: PipelineLandscapeRead,
): AppliedFilterRead[] {
  const applied: AppliedFilterRead[] = [];
  const add = (field: string, operator: AppliedFilterRead["operator"], value: AppliedFilterRead["value"]) => {
    applied.push({ field, operator, value });
  };
  const addMany = (field: string, values: string[]) => {
    if (values.length) add(field, "in", values);
  };
  const addRange = (field: string, from: string, to: string) => {
    if (from) add(field, "gte", from);
    if (to) add(field, "lte", to);
  };

  if (filters.query.trim()) add("query", "contains", filters.query.trim());
  addMany("modality", filters.modalities);
  addMany("therapeutic_area", filters.therapeuticAreas);
  addMany("innovation_type", filters.innovationTypes);
  addMany("drug_category", filters.drugCategories);
  if (filters.programStatus && filters.programStatus !== "active") add("program_status", "eq", filters.programStatus);
  if (filters.organizationRole) add("organization_role", "eq", filters.organizationRole);
  if (filters.organizationEntityId) add("organization_entity", "eq", "已选机构");
  if (filters.organizationType) add("organization_type", "eq", filters.organizationType);
  if (filters.organizationCountryRegion) add("organization_country_region", "eq", filters.organizationCountryRegion);
  if (filters.targetCombinationKey) {
    add(
      "target_combination_key",
      "eq",
      landscapeFilterLabel(landscape, "target_combinations", filters.targetCombinationKey, "已选靶点组合"),
    );
  }
  if (filters.diseaseEntityId) {
    add("disease_entity", "eq", landscapeFilterLabel(landscape, "diseases", filters.diseaseEntityId, "已选适应症"));
  }
  if (filters.phase) add("phase", "eq", filters.phase);
  if (filters.geography) add("geography", "eq", filters.geography);
  if (filters.globalPhase) add("global_phase", "eq", filters.globalPhase);
  if (filters.chinaPhase) add("china_phase", "eq", filters.chinaPhase);
  if (filters.developmentRightsRegion) add("development_rights_region", "eq", filters.developmentRightsRegion);
  if (filters.commercializationRightsRegion) {
    add("commercialization_rights_region", "eq", filters.commercializationRightsRegion);
  }
  addMany("program_tag", publicProgramTags(filters.programTags));
  if (filters.milestoneType) add("milestone_type", "eq", filters.milestoneType);
  if (filters.hasClinicalResults) add("clinical_result", "eq", filters.hasClinicalResults === "true");
  if (filters.clinicalResultEvaluation) add("clinical_result_evaluation", "eq", filters.clinicalResultEvaluation);
  if (filters.hasDeal) add("deal", "eq", filters.hasDeal === "true");
  if (filters.dealCurrency) add("deal_currency", "eq", filters.dealCurrency);
  if (filters.dealTotalPotentialAmountMin || filters.dealTotalPotentialAmountMax) {
    add(
      "deal_total_potential_amount",
      "eq",
      [filters.dealTotalPotentialAmountMin, filters.dealTotalPotentialAmountMax].filter(Boolean).join(" – "),
    );
  }
  addRange("global_phase_started_at", filters.globalPhaseStartedFrom, filters.globalPhaseStartedTo);
  addRange("china_phase_started_at", filters.chinaPhaseStartedFrom, filters.chinaPhaseStartedTo);
  addRange("status_date", filters.statusDateFrom, filters.statusDateTo);
  addRange("milestone_date", filters.milestoneFrom, filters.milestoneTo);
  return applied;
}

function pipelineLoadingLabel(targetName: string, filters: PipelineSearchFilters): string {
  const query = filters.query.trim();
  if (query) return `正在加载 ${targetName} 中与“${query}”匹配的研发项目`;
  if (filters.programStatus === "active") return `正在加载 ${targetName} 的在研项目`;
  if (filters.programStatus === "inactive") return `正在加载 ${targetName} 的已停止项目`;
  if (filters.programStatus === "unknown") return `正在加载 ${targetName} 的状态未披露项目`;
  if (hasPipelineSearchFilter({ ...filters, targetEntityId: "" })) {
    return `正在加载 ${targetName} 的筛选结果`;
  }
  return `正在加载 ${targetName} 的全部研发项目`;
}

function TargetPipeline({
  targetId,
  targetName,
  fallbackItems,
  initialFilters,
  onFiltersChange,
  onLandscapeFilterApply,
  initialDisplayMode,
  onDisplayModeChange,
  initialAnalysis,
  onAnalysisChange,
  onOpen,
  onOpenEntity,
  onOpenComparison,
}: {
  targetId: string;
  targetName: string;
  fallbackItems: CompetitiveProgram[];
  initialFilters?: PipelineSearchFilters;
  onFiltersChange?: (filters: PipelineSearchFilters) => void;
  onLandscapeFilterApply?: (filters: PipelineSearchFilters, displayMode: "drug" | "program" | "landscape") => void;
  initialDisplayMode?: "drug" | "program" | "landscape";
  onDisplayModeChange?: (displayMode: "drug" | "program" | "landscape") => void;
  initialAnalysis?: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  };
  onAnalysisChange?: (analysis: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: TargetEntityOpener;
  onOpenComparison?: (comparisonSetId: string, entityIds: string[]) => void;
}) {
  const fallbackFilters: PipelineSearchFilters = {
    ...emptyPipelineSearchFilters(),
    targetEntityId: targetId,
  };
  const effectiveInitialFilters = initialFilters ?? fallbackFilters;
  const initialFiltersKey = JSON.stringify(effectiveInitialFilters);
  const [filters, setFilters] = useState<PipelineSearchFilters>(effectiveInitialFilters);
  const lastInitialFiltersKey = useRef(initialFiltersKey);
  useEffect(() => {
    if (lastInitialFiltersKey.current === initialFiltersKey) return;
    lastInitialFiltersKey.current = initialFiltersKey;
    setFilters(effectiveInitialFilters);
  }, [effectiveInitialFilters, initialFiltersKey]);
  const effectiveInitialDisplayMode = initialDisplayMode ?? "drug";
  const initialDisplayModeKey = effectiveInitialDisplayMode;
  const [displayMode, setDisplayMode] = useState<"drug" | "program" | "landscape">(effectiveInitialDisplayMode);
  const lastInitialDisplayModeKey = useRef(initialDisplayModeKey);
  useEffect(() => {
    if (lastInitialDisplayModeKey.current === initialDisplayModeKey) return;
    lastInitialDisplayModeKey.current = initialDisplayModeKey;
    setDisplayMode(effectiveInitialDisplayMode);
  }, [effectiveInitialDisplayMode, initialDisplayModeKey]);
  const effectiveInitialAnalysis = initialAnalysis ?? {
    dimension: "all" as PipelineAnalysisDimension,
    view: "chart" as const,
    limit: 20 as PipelineAnalysisLimit,
    stageScope: "overall" as PipelineAnalysisStageScope,
    targetAggregation: "all" as PipelineTargetAggregation,
  };
  const initialAnalysisKey = JSON.stringify(effectiveInitialAnalysis);
  const [analysis, setAnalysis] = useState(effectiveInitialAnalysis);
  const lastInitialAnalysisKey = useRef(initialAnalysisKey);
  useEffect(() => {
    if (lastInitialAnalysisKey.current === initialAnalysisKey) return;
    lastInitialAnalysisKey.current = initialAnalysisKey;
    setAnalysis(effectiveInitialAnalysis);
  }, [effectiveInitialAnalysis, initialAnalysisKey]);
  const [selectedDrugIds, setSelectedDrugIds] = useState<Set<string>>(() => new Set());
  const [visibleDrugColumns, setVisibleDrugColumns] = useState<Set<TargetDrugColumnKey>>(defaultTargetDrugColumns);
  const [comparisonMessage, setComparisonMessage] = useState("");
  const [comparisonTarget, setComparisonTarget] = useState<{
    comparisonSetId: string;
    entityIds: string[];
  } | null>(null);
  const [advancedFiltersOpen, setAdvancedFiltersOpen] = useState(false);
  const targetFacetCache = useRef<{
    targetId: string;
    values: Partial<Record<TargetFacetKey, Record<string, number>>>;
  }>({ targetId, values: {} });
  if (targetFacetCache.current.targetId !== targetId) {
    targetFacetCache.current = { targetId, values: {} };
  }

  function cachedFacetOptions(
    key: TargetFacetKey,
    values: Record<string, number> | undefined,
    selected: readonly string[],
  ) {
    const cachedValues = targetFacetCache.current.values[key] ?? {};
    Object.assign(cachedValues, values ?? {});
    for (const value of selected) {
      if (!(value in cachedValues)) cachedValues[value] = values?.[value] ?? 0;
    }
    targetFacetCache.current.values[key] = cachedValues;
    return targetFacetOptions(cachedValues);
  }

  const advancedFilterCountForState = countAdvancedPipelineFilters(filters);
  useEffect(() => {
    setAdvancedFiltersOpen(advancedFilterCountForState > 0);
  }, [advancedFilterCountForState]);
  const [debouncedPipelineQuery, setDebouncedPipelineQuery] = useState(effectiveInitialFilters.query);
  useEffect(() => {
    const timeout = window.setTimeout(() => setDebouncedPipelineQuery(filters.query), 250);
    return () => window.clearTimeout(timeout);
  }, [filters.query]);
  const queryAnalysis = {
    limit: analysis.limit,
    stageScope: analysis.stageScope,
    targetAggregation: analysis.targetAggregation,
  };
  const resultGrain: PipelineResultGrain = displayMode === "program" ? "program" : "drug";
  const queryFilters =
    debouncedPipelineQuery === filters.query ? filters : { ...filters, query: debouncedPipelineQuery };
  const result = useQuery({
    queryKey: pipelineKeys.search(queryFilters, queryAnalysis, resultGrain),
    queryFn: ({ signal }) => searchPipelines(queryFilters, queryAnalysis, signal, resultGrain),
  });

  function updateFilter<Key extends keyof PipelineSearchFilters>(key: Key, value: PipelineSearchFilters[Key]) {
    setComparisonMessage("");
    const nextFilters = { ...filters, [key]: value, offset: key === "offset" ? Number(value) : 0 };
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
  }

  function updateSorting(value: string) {
    const [field, direction] = value.split(":") as [PipelineSortField, SortDirection];
    setComparisonMessage("");
    const nextFilters = {
      ...filters,
      sortBy: field,
      sortDirection: direction,
      sort: [{ field, direction }],
      offset: 0,
    };
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
  }

  function resetFilters() {
    const nextFilters = { ...emptyPipelineSearchFilters(), targetEntityId: targetId };
    setFilters(nextFilters);
    onFiltersChange?.(nextFilters);
    setComparisonMessage("");
  }

  function updateDisplayMode(nextDisplayMode: "drug" | "program" | "landscape") {
    setDisplayMode(nextDisplayMode);
    onDisplayModeChange?.(nextDisplayMode);
  }

  function updateAnalysis(nextAnalysis: typeof analysis) {
    setAnalysis(nextAnalysis);
    onAnalysisChange?.(nextAnalysis);
  }

  function applyLandscapeFilter(field: PipelineLandscapeFilterField, value: string) {
    if (field === "targetEntityId") return;
    const nextFilters = {
      ...filters,
      ...(field === "modality" ? { modalities: value ? [value] : [] } : { [field]: value }),
      offset: 0,
    };
    setComparisonMessage("");
    setFilters(nextFilters);
    setDisplayMode("drug");
    if (onLandscapeFilterApply) {
      onLandscapeFilterApply(nextFilters, "drug");
      return;
    }
    onFiltersChange?.(nextFilters);
    onDisplayModeChange?.("drug");
  }

  function toggleDrug(drugId: string, selected: boolean) {
    setSelectedDrugIds((current) => {
      const next = new Set(current);
      if (selected) next.add(drugId);
      else next.delete(drugId);
      return next;
    });
    setComparisonMessage("");
  }

  function toggleDrugColumn(column: TargetDrugColumnKey, visible: boolean) {
    setVisibleDrugColumns((current) => {
      const next = new Set(current);
      if (visible) next.add(column);
      else next.delete(column);
      return next;
    });
  }

  function togglePageDrugSelection() {
    setSelectedDrugIds((current) => {
      const next = new Set(current);
      if (allPageDrugsSelected) {
        pageDrugIds.forEach((drugId) => {
          next.delete(drugId);
        });
      } else {
        pageDrugIds.forEach((drugId) => {
          next.add(drugId);
        });
      }
      return next;
    });
    setComparisonMessage("");
  }

  function clearDrugSelection() {
    setSelectedDrugIds(new Set());
    setComparisonMessage("");
  }

  if (result.isPending) {
    return <Spinner label={pipelineLoadingLabel(targetName, filters)} />;
  }
  if (result.error || !result.data) {
    return (
      <div>
        <ErrorState
          message={result.error instanceof Error ? result.error.message : "研发项目查询失败"}
          retry={() => void result.refetch()}
        />
        {fallbackItems.length ? (
          <>
            <p className="inline-alert">当前仅显示档案缓存中的部分记录，完整结果暂不可用。</p>
            <Pipeline items={fallbackItems} onOpen={onOpen} onOpenEntity={onOpenEntity} />
          </>
        ) : null}
      </div>
    );
  }

  const data = result.data;
  const hasUserFilters = hasPipelineSearchFilter({
    ...filters,
    targetEntityId: "",
    programStatus: filters.programStatus === "active" ? "" : filters.programStatus,
  });
  const rangeStart = data.total ? data.offset + 1 : 0;
  const rangeEnd = Math.min(data.offset + data.items.length, data.total);
  const pageDrugIds =
    displayMode === "drug"
      ? [...new Set(data.items.map((item) => item.drug_entity_id).filter((value): value is string => Boolean(value)))]
      : [];
  const selectedPageDrugCount = pageDrugIds.filter((drugId) => selectedDrugIds.has(drugId)).length;
  const allPageDrugsSelected = pageDrugIds.length > 0 && selectedPageDrugCount === pageDrugIds.length;
  const advancedFilterCount = countAdvancedPipelineFilters(filters);
  const clinicalResultCount = data.facets?.has_clinical_results?.true ?? 0;
  const dealDisclosureCount = data.facets?.has_deal?.true ?? 0;
  const hasNoRelatedCoverage =
    data.total > 0 &&
    data.landscape.distinct_diseases === 0 &&
    data.landscape.distinct_organizations === 0 &&
    clinicalResultCount === 0 &&
    dealDisclosureCount === 0;
  const programTagOptions = cachedFacetOptions("program_tag", data.facets?.program_tag, filters.programTags)
    .filter((option) => isPublicProgramTag(option.value))
    .map((option) => ({ ...option, label: programTagLabel(option.value) }));

  return (
    <div className="target-pipeline-panel">
      <section className="result-summary" aria-label={`${targetName} 研发药物概览`}>
        <span>
          <strong>{(data.project_total ?? data.landscape.total_programs).toLocaleString("zh-CN")}</strong> 个研发项目
        </span>
        <span>
          <strong>{data.landscape.distinct_drugs.toLocaleString("zh-CN")}</strong> 个药物
        </span>
      </section>
      <p className="muted-text">
        当前显示 {rangeStart}-{rangeEnd} · 数据截至 {formatDate(data.as_of)}
        {data.result_grain === "drug"
          ? "。默认按药物汇总全部匹配适应症；可切换项目明细查看每条研发记录。"
          : "。项目明细按药物-适应症展示，加入比较时按药物去重。"}
      </p>
      <section className="pipeline-coverage-summary" aria-label="结果覆盖范围">
        <p className="muted-text">
          {`关联适应症 ${data.landscape.distinct_diseases.toLocaleString("zh-CN")} 个 · 研发机构 ${data.landscape.distinct_organizations.toLocaleString("zh-CN")} 家 · 临床结果 ${clinicalResultCount.toLocaleString("zh-CN")} 条 · 交易披露 ${dealDisclosureCount.toLocaleString("zh-CN")} 条`}
        </p>
      </section>
      {hasNoRelatedCoverage ? (
        <p className="inline-alert">
          当前结果暂未关联适应症、研发机构、临床结果或交易披露。结果数量反映当前可检索来源中的匹配记录，不代表相关信息不存在。
        </p>
      ) : null}
      <div className="pipeline-result-actions query-results-toolbar">
        <fieldset className="segmented-control">
          <legend className="sr-only">研发药物展示方式</legend>
          <button type="button" aria-pressed={displayMode === "drug"} onClick={() => updateDisplayMode("drug")}>
            药物概览
          </button>
          <button type="button" aria-pressed={displayMode === "program"} onClick={() => updateDisplayMode("program")}>
            项目明细
          </button>
          <button
            type="button"
            aria-pressed={displayMode === "landscape"}
            onClick={() => updateDisplayMode("landscape")}
          >
            可视化
          </button>
        </fieldset>
        {displayMode === "drug" ? (
          <details className="table-column-menu">
            <summary>
              <Columns3 size={15} />列
            </summary>
            <fieldset>
              <legend>药物概览列设置</legend>
              {targetDrugColumnOptions.map((column) => (
                <label className="table-column-option" key={column.key}>
                  <input
                    type="checkbox"
                    aria-label={`显示列：${column.label}`}
                    checked={visibleDrugColumns.has(column.key)}
                    onChange={(event) => toggleDrugColumn(column.key, event.target.checked)}
                  />
                  <span>{column.label}</span>
                </label>
              ))}
              <button
                className="secondary-button"
                type="button"
                disabled={visibleDrugColumns.size === targetDrugColumnOptions.length}
                onClick={() => setVisibleDrugColumns(defaultTargetDrugColumns())}
              >
                <RotateCcw size={14} />
                恢复默认列
              </button>
            </fieldset>
          </details>
        ) : null}
        <AddToComparisonControl
          selectedEntityIds={[...selectedDrugIds]}
          onAdded={(message) => {
            setSelectedDrugIds(new Set());
            setComparisonMessage(message);
            setComparisonTarget(null);
          }}
          onComparisonReady={
            onOpenComparison
              ? (comparisonSetId, entityIds) => setComparisonTarget({ comparisonSetId, entityIds })
              : undefined
          }
        />
        {displayMode === "drug" ? (
          <div className="table-selection-actions pipeline-result-actions" role="toolbar" aria-label="竞品候选选择">
            <span role="status">
              {selectedDrugIds.size
                ? `已选 ${selectedDrugIds.size} 个药物，可继续调整筛选添加其他候选`
                : "尚未选择药物"}
            </span>
            <button
              className="secondary-button"
              type="button"
              disabled={!pageDrugIds.length}
              aria-pressed={allPageDrugsSelected}
              onClick={togglePageDrugSelection}
            >
              {allPageDrugsSelected ? "取消选择本页" : "选择本页"}
            </button>
            {selectedDrugIds.size ? (
              <button className="secondary-button" type="button" onClick={clearDrugSelection}>
                清空选择
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
      {comparisonMessage ? (
        <p className="inline-success" role="status">
          {comparisonMessage}
          {comparisonTarget && onOpenComparison ? (
            <button
              className="text-button"
              type="button"
              onClick={() => onOpenComparison(comparisonTarget.comparisonSetId, comparisonTarget.entityIds)}
            >
              打开对比列表
            </button>
          ) : null}
        </p>
      ) : null}
      <fieldset className="target-evidence-filters">
        <legend className="sr-only">研发项目筛选</legend>
        <label>
          药物或机构
          <input
            type="search"
            value={filters.query}
            placeholder="输入药物、公司或适应症"
            onChange={(event) => updateFilter("query", event.target.value)}
          />
        </label>
        <FacetMultiSelect
          label="药物类型"
          options={cachedFacetOptions("modality", data.facets?.modality, filters.modalities).map((option) => ({
            ...option,
            label: programModalityLabel(option.value),
          }))}
          selected={filters.modalities}
          onChange={(values) => updateFilter("modalities", values)}
        />
        <FacetMultiSelect
          label="适应症领域"
          options={cachedFacetOptions("therapeutic_area", data.facets?.therapeutic_area, filters.therapeuticAreas)}
          selected={filters.therapeuticAreas}
          onChange={(values) => updateFilter("therapeuticAreas", values)}
        />
        <TargetPipelineSelect
          label="最高阶段"
          value={filters.phase}
          values={data.facets?.phase}
          onChange={(value) => updateFilter("phase", value)}
          formatItem={developmentPhaseLabel}
        />
        <TargetPipelineSelect
          label="地区"
          value={filters.geography}
          values={data.facets?.geography}
          onChange={(value) => updateFilter("geography", value)}
          formatItem={geographyLabel}
        />
        <label>
          项目状态
          <select value={filters.programStatus} onChange={(event) => updateFilter("programStatus", event.target.value)}>
            <option value="">全部</option>
            <option
              value="active"
              disabled={isUnavailableFacetOption(
                data.facets?.program_status?.active ?? 0,
                "active",
                filters.programStatus,
              )}
            >
              在研 ({data.facets?.program_status?.active ?? 0})
            </option>
            <option
              value="inactive"
              disabled={isUnavailableFacetOption(
                data.facets?.program_status?.inactive ?? 0,
                "inactive",
                filters.programStatus,
              )}
            >
              已停止 ({data.facets?.program_status?.inactive ?? 0})
            </option>
            <option
              value="unknown"
              disabled={isUnavailableFacetOption(
                data.facets?.program_status?.unknown ?? 0,
                "unknown",
                filters.programStatus,
              )}
            >
              状态未披露 ({data.facets?.program_status?.unknown ?? 0})
            </option>
          </select>
        </label>
        <label>
          临床结果
          <select
            value={filters.hasClinicalResults}
            onChange={(event) => {
              const value = event.target.value as PipelineSearchFilters["hasClinicalResults"];
              const nextFilters = {
                ...filters,
                hasClinicalResults: value,
                clinicalResultEvaluation: value === "false" ? "" : filters.clinicalResultEvaluation,
                offset: 0,
              };
              setFilters(nextFilters);
              onFiltersChange?.(nextFilters);
              setComparisonMessage("");
            }}
          >
            <option value="">全部</option>
            <option
              value="true"
              disabled={isUnavailableFacetOption(
                data.facets?.has_clinical_results?.true ?? 0,
                "true",
                filters.hasClinicalResults,
              )}
            >
              已有结果 ({data.facets?.has_clinical_results?.true ?? 0})
            </option>
            <option
              value="false"
              disabled={isUnavailableFacetOption(
                data.facets?.has_clinical_results?.false ?? 0,
                "false",
                filters.hasClinicalResults,
              )}
            >
              暂无结果 ({data.facets?.has_clinical_results?.false ?? 0})
            </option>
          </select>
        </label>
        <label>
          交易信号
          <select
            value={filters.hasDeal}
            onChange={(event) => {
              const value = event.target.value as PipelineSearchFilters["hasDeal"];
              const nextFilters = {
                ...filters,
                hasDeal: value,
                dealCurrency: value === "false" ? "" : filters.dealCurrency,
                dealTotalPotentialAmountMin: value === "false" ? "" : filters.dealTotalPotentialAmountMin,
                dealTotalPotentialAmountMax: value === "false" ? "" : filters.dealTotalPotentialAmountMax,
                offset: 0,
              };
              setFilters(nextFilters);
              onFiltersChange?.(nextFilters);
              setComparisonMessage("");
            }}
          >
            <option value="">全部</option>
            <option
              value="true"
              disabled={isUnavailableFacetOption(data.facets?.has_deal?.true ?? 0, "true", filters.hasDeal)}
            >
              已有交易 ({data.facets?.has_deal?.true ?? 0})
            </option>
            <option
              value="false"
              disabled={isUnavailableFacetOption(data.facets?.has_deal?.false ?? 0, "false", filters.hasDeal)}
            >
              暂无交易 ({data.facets?.has_deal?.false ?? 0})
            </option>
          </select>
        </label>
        <label>
          排序方式
          <select
            value={`${filters.sortBy}:${filters.sortDirection}`}
            onChange={(event) => updateSorting(event.target.value)}
          >
            <option value="status_date:desc">最近更新</option>
            <option value="phase:desc">最高阶段优先</option>
            <option value="global_phase:desc">全球阶段优先</option>
            <option value="china_phase:desc">中国阶段优先</option>
            <option value="global_phase_started_at:desc">全球阶段开始日期</option>
            <option value="china_phase_started_at:desc">中国阶段开始日期</option>
            <option value="drug_name:asc">药物名称</option>
            <option value="organization_name:asc">研发机构</option>
            <option value="disease_name:asc">适应症</option>
            <option value="modality:asc">药物类型</option>
            <option value="mechanism_of_action:asc">作用机制</option>
          </select>
        </label>
        <button type="button" onClick={resetFilters} disabled={!hasUserFilters}>
          重置筛选
        </button>
      </fieldset>
      <AppliedFiltersBar
        filters={targetPipelineAppliedFilters(filters, data.landscape)}
        labels={targetPipelineAppliedFilterLabels}
        valueLabels={{
          modality: Object.fromEntries(filters.modalities.map((value) => [value, programModalityLabel(value)])),
          program_tag: Object.fromEntries(
            publicProgramTags(filters.programTags).map((value) => [value, programTagLabel(value)]),
          ),
          program_status: { inactive: "已停止", unknown: "状态未披露" },
          phase: developmentPhaseLabels,
          global_phase: developmentPhaseLabels,
          china_phase: developmentPhaseLabels,
          geography: geographyLabels,
          clinical_result: { true: "已有结果", false: "暂无结果" },
          deal: { true: "已有交易", false: "暂无交易" },
        }}
        onClear={hasUserFilters ? resetFilters : undefined}
      />
      <details
        className="advanced-filter-panel pipeline-advanced-filters"
        open={advancedFiltersOpen}
        onToggle={(event) => setAdvancedFiltersOpen(event.currentTarget.open)}
      >
        <summary>
          <span>更多筛选</span>
          <span>{advancedFilterCount ? `已选 ${advancedFilterCount} 项` : "创新、机构、区域阶段与时间"}</span>
        </summary>
        <div className="pipeline-advanced-grid">
          <FacetMultiSelect
            label="创新类型"
            options={cachedFacetOptions("innovation_type", data.facets?.innovation_type, filters.innovationTypes)}
            selected={filters.innovationTypes}
            onChange={(values) => updateFilter("innovationTypes", values)}
          />
          <FacetMultiSelect
            label="药品类别"
            options={cachedFacetOptions("drug_category", data.facets?.drug_category, filters.drugCategories)}
            selected={filters.drugCategories}
            onChange={(values) => updateFilter("drugCategories", values)}
          />
          <TargetPipelineSelect
            label="机构角色"
            value={filters.organizationRole}
            values={data.facets?.organization_role}
            onChange={(value) => updateFilter("organizationRole", value)}
            formatItem={organizationRoleLabel}
          />
          <EntityFilterSelect
            label="研发机构"
            entityType="organization"
            value={filters.organizationEntityId}
            onChange={(value) => updateFilter("organizationEntityId", value)}
            placeholder="输入至少 2 个字符查找机构"
          />
          <TargetPipelineSelect
            label="机构标签"
            value={filters.organizationType}
            values={data.facets?.organization_type}
            onChange={(value) => updateFilter("organizationType", value)}
          />
          <TargetPipelineSelect
            label="机构所在地区"
            value={filters.organizationCountryRegion}
            values={data.facets?.organization_country_region}
            onChange={(value) => updateFilter("organizationCountryRegion", value)}
          />
          <TargetPipelineSelect
            label="全球最高阶段"
            value={filters.globalPhase}
            values={data.facets?.global_phase}
            onChange={(value) => updateFilter("globalPhase", value)}
            formatItem={developmentPhaseLabel}
          />
          <TargetPipelineSelect
            label="中国最高阶段"
            value={filters.chinaPhase}
            values={data.facets?.china_phase}
            onChange={(value) => updateFilter("chinaPhase", value)}
            formatItem={developmentPhaseLabel}
          />
          <TargetPipelineSelect
            label="研发权益地区"
            value={filters.developmentRightsRegion}
            values={data.facets?.development_rights_region}
            onChange={(value) => updateFilter("developmentRightsRegion", value)}
          />
          <TargetPipelineSelect
            label="商业化权益地区"
            value={filters.commercializationRightsRegion}
            values={data.facets?.commercialization_rights_region}
            onChange={(value) => updateFilter("commercializationRightsRegion", value)}
          />
          {programTagOptions.length || filters.programTags.length ? (
            <FacetMultiSelect
              label="项目标签"
              options={programTagOptions}
              selected={filters.programTags}
              onChange={(values) => updateFilter("programTags", values)}
            />
          ) : null}
          <TargetPipelineSelect
            label="里程碑类型"
            value={filters.milestoneType}
            values={data.facets?.milestone_type}
            onChange={(value) => updateFilter("milestoneType", value)}
          />
          <TargetPipelineSelect
            label="临床结果评价"
            value={filters.clinicalResultEvaluation}
            values={data.facets?.clinical_result_evaluation}
            onChange={(value) => updateFilter("clinicalResultEvaluation", value)}
            formatItem={(value) => pipelineResultEvaluationLabels[value] ?? value}
            disabled={filters.hasClinicalResults === "false"}
          />
          <TargetPipelineSelect
            label="交易币种"
            value={filters.dealCurrency}
            values={data.facets?.deal_currency}
            onChange={(value) => updateFilter("dealCurrency", value)}
            disabled={filters.hasDeal === "false"}
          />
          <label>
            潜在交易总额下限
            <input
              type="number"
              min="0"
              step="0.01"
              inputMode="decimal"
              disabled={filters.hasDeal === "false"}
              value={filters.dealTotalPotentialAmountMin}
              onChange={(event) => updateFilter("dealTotalPotentialAmountMin", event.target.value)}
              placeholder="例如 100000000"
            />
          </label>
          <label>
            潜在交易总额上限
            <input
              type="number"
              min={filters.dealTotalPotentialAmountMin || "0"}
              step="0.01"
              inputMode="decimal"
              disabled={filters.hasDeal === "false"}
              value={filters.dealTotalPotentialAmountMax}
              onChange={(event) => updateFilter("dealTotalPotentialAmountMax", event.target.value)}
              placeholder="例如 500000000"
            />
          </label>
          <TargetPipelineDateRange
            legend="全球阶段开始日期"
            from={filters.globalPhaseStartedFrom}
            to={filters.globalPhaseStartedTo}
            onFromChange={(value) => updateFilter("globalPhaseStartedFrom", value)}
            onToChange={(value) => updateFilter("globalPhaseStartedTo", value)}
          />
          <TargetPipelineDateRange
            legend="中国阶段开始日期"
            from={filters.chinaPhaseStartedFrom}
            to={filters.chinaPhaseStartedTo}
            onFromChange={(value) => updateFilter("chinaPhaseStartedFrom", value)}
            onToChange={(value) => updateFilter("chinaPhaseStartedTo", value)}
          />
          <TargetPipelineDateRange
            legend="状态更新日期"
            from={filters.statusDateFrom}
            to={filters.statusDateTo}
            onFromChange={(value) => updateFilter("statusDateFrom", value)}
            onToChange={(value) => updateFilter("statusDateTo", value)}
          />
          <TargetPipelineDateRange
            legend="里程碑日期"
            from={filters.milestoneFrom}
            to={filters.milestoneTo}
            onFromChange={(value) => updateFilter("milestoneFrom", value)}
            onToChange={(value) => updateFilter("milestoneTo", value)}
          />
        </div>
      </details>
      {(data.warnings ?? []).map((warning) => (
        <p className="inline-alert" key={warning}>
          {warning}
        </p>
      ))}
      {displayMode === "landscape" ? (
        <PipelineLandscape
          landscape={data.landscape}
          dimension={analysis.dimension}
          view={analysis.view}
          limit={analysis.limit}
          stageScope={analysis.stageScope}
          targetAggregation={analysis.targetAggregation}
          onFilter={applyLandscapeFilter}
          onOpenEntity={(entityId) => onOpenEntity("drug", entityId)}
          onOpenTarget={(entityId) => onOpenEntity("target", entityId)}
          onOpenDisease={(entityId) => onOpenEntity("disease", entityId)}
          onOpenOrganization={(entityId) => onOpenEntity("organization", entityId)}
          onAnalysisChange={updateAnalysis}
        />
      ) : data.items.length ? (
        <>
          {data.result_grain === "drug" ? (
            <DrugPipeline
              items={data.items}
              onOpenEntity={onOpenEntity}
              selectedDrugIds={selectedDrugIds}
              onToggleDrug={toggleDrug}
              visibleColumns={visibleDrugColumns}
            />
          ) : (
            <Pipeline
              items={data.items}
              onOpen={onOpen}
              onOpenEntity={onOpenEntity}
              selectedDrugIds={selectedDrugIds}
              onToggleDrug={toggleDrug}
            />
          )}
          <nav className="sar-pagination" aria-label="研发药物分页">
            <button
              type="button"
              disabled={data.offset === 0}
              onClick={() => updateFilter("offset", Math.max(0, data.offset - data.limit))}
            >
              上一页
            </button>
            <span>
              {rangeStart}-{rangeEnd} / {data.total.toLocaleString("zh-CN")}
            </span>
            <button
              type="button"
              disabled={data.offset + data.items.length >= data.total}
              onClick={() => updateFilter("offset", data.offset + data.limit)}
            >
              下一页
            </button>
          </nav>
        </>
      ) : (
        <EmptyState
          title={hasUserFilters ? "当前筛选条件下暂无匹配研发项目" : `暂无 ${targetName} 研发项目记录`}
          detail={
            hasUserFilters
              ? "调整或重置筛选条件后重试"
              : "当前暂无可公开展示的研发项目记录；来源资料正在完成质量核查或尚未覆盖该靶点。"
          }
        />
      )}
    </div>
  );
}

function DrugPipeline({
  items,
  onOpenEntity,
  selectedDrugIds,
  onToggleDrug,
  visibleColumns,
}: {
  items: CompetitiveProgram[];
  onOpenEntity: TargetEntityOpener;
  selectedDrugIds: Set<string>;
  onToggleDrug: (drugId: string, selected: boolean) => void;
  visibleColumns: Set<TargetDrugColumnKey>;
}) {
  return (
    <ScrollableTableRegion ariaLabel="靶点研发药物概览">
      <table aria-label="靶点研发药物概览">
        <thead>
          <tr>
            <th scope="col">对比</th>
            <th scope="col">药物</th>
            {visibleColumns.has("organizations") ? <th scope="col">研发机构</th> : null}
            {visibleColumns.has("targets") ? <th scope="col">靶点组合</th> : null}
            {visibleColumns.has("mechanism") ? <th scope="col">类型 / 机制</th> : null}
            {visibleColumns.has("indications") ? <th scope="col">适应症与阶段</th> : null}
            {visibleColumns.has("global_phase") ? <th scope="col">全球最高阶段</th> : null}
            {visibleColumns.has("china_phase") ? <th scope="col">中国最高阶段</th> : null}
            {visibleColumns.has("status") ? <th scope="col">项目状态</th> : null}
            {visibleColumns.has("clinical") ? <th scope="col">临床结果</th> : null}
            {visibleColumns.has("innovation") ? <th scope="col">创新类型</th> : null}
            {visibleColumns.has("updated") ? <th scope="col">最近更新</th> : null}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => {
            const organizations = item.organizations ?? [];
            const targets = item.targets ?? [];
            const indications = item.indications ?? [];
            const statuses = item.program_status_counts ?? {};
            return (
              <tr key={item.drug_entity_id}>
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择对比 ${item.drug_name}`}
                    checked={selectedDrugIds.has(item.drug_entity_id)}
                    onChange={(event) => onToggleDrug(item.drug_entity_id, event.target.checked)}
                  />
                </td>
                <td>
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => onOpenEntity("drug", item.drug_entity_id)}
                  >
                    {item.drug_name}
                  </button>
                  <small> · {item.project_count ?? indications.length} 个研发项目</small>
                </td>
                {visibleColumns.has("organizations") ? (
                  <td>
                    {organizations.length
                      ? organizations.map((organization, index) => (
                          <span key={organization.entity_id}>
                            {index ? "、" : ""}
                            <button
                              className="table-link-button"
                              type="button"
                              onClick={() => onOpenEntity("organization", organization.entity_id)}
                            >
                              {organization.name}
                            </button>
                            <small>{organization.role ? `（${organizationRoleLabel(organization.role)}）` : ""}</small>
                          </span>
                        ))
                      : (item.organization_name ?? "--")}
                  </td>
                ) : null}
                {visibleColumns.has("targets") ? (
                  <td>
                    {targets.length
                      ? targets.map((target, index) => (
                          <span key={target.entity_id}>
                            {index ? " + " : ""}
                            <button
                              className="table-link-button"
                              type="button"
                              onClick={() => onOpenEntity("target", target.entity_id)}
                            >
                              {target.name}
                            </button>
                          </span>
                        ))
                      : (item.target_name ?? "--")}
                  </td>
                ) : null}
                {visibleColumns.has("mechanism") ? (
                  <td>
                    {(item.modalities ?? []).map(programModalityLabel).join("、") || "--"}
                    {(item.mechanisms_of_action ?? []).length ? (
                      <small> · 机制：{(item.mechanisms_of_action ?? []).join("；")}</small>
                    ) : null}
                  </td>
                ) : null}
                {visibleColumns.has("indications") ? (
                  <td>
                    {indications.length ? (
                      <ul className="program-history indication-preview" aria-label={`${item.drug_name} 适应症与阶段`}>
                        {indications.slice(0, 2).map((indication) => (
                          <li key={indication.program_id}>
                            {indication.disease_entity_id && indication.disease_name ? (
                              <button
                                className="table-link-button"
                                type="button"
                                onClick={() => onOpenEntity("disease", indication.disease_entity_id as string)}
                              >
                                {indication.disease_name}
                              </button>
                            ) : (
                              "适应症未披露"
                            )}{" "}
                            <StatusBadge value={developmentPhaseLabel(indication.phase)} />
                          </li>
                        ))}
                        {indications.length > 2 ? (
                          <details className="program-history">
                            <summary>查看其余 {indications.length - 2} 个适应症项目</summary>
                            <ol>
                              {indications.slice(2).map((indication) => (
                                <li key={indication.program_id}>
                                  {indication.disease_entity_id && indication.disease_name ? (
                                    <button
                                      className="table-link-button"
                                      type="button"
                                      onClick={() => onOpenEntity("disease", indication.disease_entity_id as string)}
                                    >
                                      {indication.disease_name}
                                    </button>
                                  ) : (
                                    "适应症未披露"
                                  )}{" "}
                                  <StatusBadge value={developmentPhaseLabel(indication.phase)} />
                                </li>
                              ))}
                            </ol>
                          </details>
                        ) : null}
                      </ul>
                    ) : (
                      <span>适应症未披露</span>
                    )}
                  </td>
                ) : null}
                {visibleColumns.has("global_phase") ? (
                  <td>
                    <StatusBadge value={developmentPhaseLabel(item.global_phase ?? item.phase)} />
                    {item.global_phase_started_at ? <small> · {formatDate(item.global_phase_started_at)}</small> : null}
                  </td>
                ) : null}
                {visibleColumns.has("china_phase") ? (
                  <td>
                    {item.china_phase ? <StatusBadge value={developmentPhaseLabel(item.china_phase)} /> : "--"}
                    {item.china_phase_started_at ? <small> · {formatDate(item.china_phase_started_at)}</small> : null}
                  </td>
                ) : null}
                {visibleColumns.has("status") ? (
                  <td>
                    <span className="status-badge">{pipelineProgramStatusLabel(item)}</span>
                    <small>
                      {" "}
                      · 在研 {statuses.active ?? 0} · 已停止 {statuses.inactive ?? 0} · 未披露 {statuses.unknown ?? 0}
                    </small>
                  </td>
                ) : null}
                {visibleColumns.has("clinical") ? (
                  <td>
                    {item.has_clinical_results ? "已有结果" : "暂无结果"}
                    <small> · {item.clinical_trial_count ?? 0} 项临床试验</small>
                  </td>
                ) : null}
                {visibleColumns.has("innovation") ? <td>{(item.innovation_types ?? []).join("、") || "--"}</td> : null}
                {visibleColumns.has("updated") ? <td>{formatDate(item.status_date)}</td> : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

const organizationRoleLabels: Record<string, string> = {
  originator: "原研方",
  collaborator: "合作方",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

function organizationRoleLabel(value: string): string {
  return organizationRoleLabels[value] ?? "其他";
}

function programStatusLabel(value: CompetitiveProgram["program_status"] | string | null | undefined): string {
  const normalized = value?.toLowerCase();
  if (normalized === "active") return "在研";
  if (normalized === "inactive") return "已停止";
  return "状态未披露";
}

export function pipelineProgramStatusLabel(
  program: Pick<CompetitiveProgram, "program_status" | "program_status_counts">,
): string {
  const states = Object.entries(program.program_status_counts ?? {}).filter(([, count]) => count > 0);
  return states.length > 1 ? "混合状态" : programStatusLabel(program.program_status);
}

const developmentPhaseLabels: Record<string, string> = {
  discovery: "药物发现",
  preclinical: "临床前",
  ind: "IND",
  phase_1: "I 期",
  phase_1_2: "I/II 期",
  phase_2: "II 期",
  phase_2_3: "II/III 期",
  phase_3: "III 期",
  filed: "申报上市",
  approved: "已批准",
  discontinued: "已终止",
};

function developmentPhaseLabel(value: string): string {
  return developmentPhaseLabels[value.toLowerCase()] ?? value;
}

type TargetFacetKey = "modality" | "therapeutic_area" | "innovation_type" | "drug_category" | "program_tag";

function targetFacetOptions(values: Record<string, number> | undefined) {
  return Object.entries(values ?? {}).map(([value, count]) => ({ value, label: value, count }));
}

const geographyLabels: Record<string, string> = {
  global: "全球",
  china: "中国",
  us: "美国",
  europe: "欧洲",
};

function geographyLabel(value: string): string {
  return geographyLabels[value.toLowerCase()] ?? value;
}

function TargetPipelineSelect({
  label,
  value,
  values,
  onChange,
  formatItem = (item) => item,
  disabled = false,
}: {
  label: string;
  value: string;
  values: Record<string, number> | undefined;
  onChange: (value: string) => void;
  formatItem?: (value: string) => string;
  disabled?: boolean;
}) {
  const options = pipelineSelectOptions(value, values);
  return (
    <label>
      {label}
      <select value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)}>
        <option value="">全部</option>
        {options.map(([item, count]) => (
          <option value={item} key={item} disabled={isUnavailableFacetOption(count, item, value)}>
            {formatItem(item)} ({count})
          </option>
        ))}
      </select>
    </label>
  );
}

export function pipelineSelectOptions(value: string, values: Record<string, number> | undefined): [string, number][] {
  const options = { ...(values ?? {}) };
  if (value && !(value in options)) options[value] = 0;
  return Object.entries(options);
}

function isUnavailableFacetOption(count: number, optionValue: string, selectedValue: string): boolean {
  return count <= 0 && optionValue !== selectedValue;
}

function TargetPipelineDateRange({
  legend,
  from,
  to,
  onFromChange,
  onToChange,
}: {
  legend: string;
  from: string;
  to: string;
  onFromChange: (value: string) => void;
  onToChange: (value: string) => void;
}) {
  return (
    <fieldset className="date-range-fieldset">
      <legend>{legend}</legend>
      <label>
        <span>起</span>
        <input
          type="date"
          aria-label={`${legend}起`}
          value={from}
          max={to || undefined}
          onChange={(event) => onFromChange(event.target.value)}
        />
      </label>
      <label>
        <span>止</span>
        <input
          type="date"
          aria-label={`${legend}止`}
          value={to}
          min={from || undefined}
          onChange={(event) => onToChange(event.target.value)}
        />
      </label>
    </fieldset>
  );
}

function Pipeline({
  items,
  onOpen,
  onOpenEntity,
  selectedDrugIds,
  onToggleDrug,
}: {
  items: CompetitiveProgram[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: TargetEntityOpener;
  selectedDrugIds?: Set<string>;
  onToggleDrug?: (drugId: string, selected: boolean) => void;
}) {
  if (!items.length) return <EmptyState title="暂无竞品管线记录" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点竞品研发管线">
      <table aria-label="靶点竞品研发管线">
        <thead>
          <tr>
            {onToggleDrug ? <th scope="col">对比</th> : null}
            <th>药物</th>
            <th>公司</th>
            <th>适应症</th>
            <th>机制/模态</th>
            <th>阶段</th>
            <th>状态日期</th>
            <th>阶段历史与里程碑</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              {onToggleDrug ? (
                <td>
                  <input
                    type="checkbox"
                    aria-label={`选择对比 ${item.drug_name}`}
                    checked={selectedDrugIds?.has(item.drug_entity_id) ?? false}
                    onChange={(event) => onToggleDrug(item.drug_entity_id, event.target.checked)}
                  />
                </td>
              ) : null}
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenEntity("drug", item.drug_entity_id)}
                >
                  {item.drug_name}
                </button>
              </td>
              <td>
                {item.organization_entity_id && item.organization_name ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => onOpenEntity("organization", item.organization_entity_id as string)}
                  >
                    {item.organization_name}
                  </button>
                ) : (
                  "--"
                )}
              </td>
              <td>
                {item.disease_entity_id && item.disease_name ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => onOpenEntity("disease", item.disease_entity_id as string)}
                  >
                    {item.disease_name}
                  </button>
                ) : (
                  "--"
                )}
              </td>
              <td>{item.mechanism_of_action ?? item.modality ?? "--"}</td>
              <td>
                <StatusBadge value={developmentPhaseLabel(item.phase)} />
              </td>
              <td>{formatDate(item.status_date)}</td>
              <td>
                <details className="program-history">
                  <summary>
                    {item.status_history?.length ?? 0} 个阶段 · {item.milestones?.length ?? 0} 个里程碑
                  </summary>
                  <ol>
                    {item.status_history?.map((event) => (
                      <li key={`${event.phase}-${event.effective_at}-${event.geography ?? "global"}`}>
                        <strong>{developmentPhaseLabel(event.phase)}</strong> · {formatDate(event.effective_at)}
                        {event.geography ? ` · ${geographyLabel(event.geography)}` : ""}
                        {event.status ? ` · ${programStatusLabel(event.status)}` : ""}
                      </li>
                    ))}
                    {item.milestones?.map((event) => (
                      <li key={`${event.milestone_type}-${event.occurred_at}-${event.title}`}>
                        <strong>{event.title}</strong> · {formatDate(event.occurred_at)}
                        {event.geography ? ` · ${geographyLabel(event.geography)}` : ""}
                      </li>
                    ))}
                  </ol>
                </details>
              </td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "development_program", resourceId: item.id, label: item.drug_name }}
                  onOpen={onOpen}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

function Trials({
  items,
  onOpen,
  onOpenTrial,
}: {
  items: ClinicalTrial[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
}) {
  const pageSize = 10;
  const [visibleCount, setVisibleCount] = useState(Math.min(pageSize, items.length));
  useEffect(() => {
    setVisibleCount(Math.min(pageSize, items.length));
  }, [items]);
  if (!items.length) return <EmptyState title="暂无关联临床试验" />;
  const visibleItems = items.slice(0, visibleCount);
  const remainingCount = items.length - visibleItems.length;
  return (
    <div>
      <p className="result-summary" role="status" aria-live="polite">
        当前显示 {visibleItems.length} / 共 {items.length} 项临床试验
      </p>
      <div className="record-list">
        {visibleItems.map((item) => (
          <TrialRecord key={item.id} item={item} onOpen={onOpen} onOpenTrial={onOpenTrial} />
        ))}
      </div>
      {items.length > pageSize ? (
        <nav className="sar-pagination" aria-label="靶点临床试验分段浏览">
          {remainingCount ? (
            <button
              className="secondary-button"
              type="button"
              onClick={() => setVisibleCount((count) => Math.min(count + pageSize, items.length))}
            >
              继续显示 {Math.min(pageSize, remainingCount)} 项
            </button>
          ) : (
            <button className="secondary-button" type="button" onClick={() => setVisibleCount(pageSize)}>
              收起至前 {pageSize} 项
            </button>
          )}
        </nav>
      ) : null}
    </div>
  );
}

function TrialRecord({
  item,
  onOpen,
  onOpenTrial,
}: {
  item: ClinicalTrial;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
}) {
  const [showAllConditions, setShowAllConditions] = useState(false);
  const collapsibleConditions = item.conditions.length > 3;
  const visibleConditions = showAllConditions ? item.conditions : item.conditions.slice(0, 3);

  return (
    <article>
      <div className="record-icon">
        <CalendarDays size={18} />
      </div>
      <div>
        <span className="record-kicker">
          {item.registry_id} · {item.phases.map(clinicalTrialPhaseLabel).join(" / ") || "阶段未记录"}
        </span>
        <h3>
          <button className="table-link-button" type="button" onClick={() => onOpenTrial(item.id)}>
            {item.official_title}
          </button>
        </h3>
        <p>{visibleConditions.join("、") || "适应症未记录"}</p>
        {collapsibleConditions ? (
          <button
            className="text-button"
            type="button"
            aria-expanded={showAllConditions}
            onClick={() => setShowAllConditions((value) => !value)}
          >
            {showAllConditions ? "收起适应症" : `查看全部 ${item.conditions.length} 项适应症`}
          </button>
        ) : null}
        <div className="record-meta">
          <span>入组 {item.enrollment ?? "--"}</span>
          <span>{item.sponsors.map(stringifyParty).join("、") || "申办方未记录"}</span>
          <span>
            {formatDate(item.start_date)} - {formatDate(item.completion_date)}
          </span>
        </div>
      </div>
      <StatusBadge value={item.overall_status ?? "UNKNOWN"} label={clinicalTrialStatusLabel(item.overall_status)} />
      <ProvenanceButton
        selection={{ resourceType: "clinical_trial", resourceId: item.id, label: item.registry_id }}
        onOpen={onOpen}
      />
    </article>
  );
}

function Patents({
  items,
  onOpen,
  onOpenPatent,
}: {
  items: PatentFamily[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenPatent: (patentId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联专利族" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点关联专利族">
      <table aria-label="靶点关联专利族">
        <thead>
          <tr>
            <th>专利族</th>
            <th>标题</th>
            <th>申请人</th>
            <th>优先权日</th>
            <th>法律状态</th>
            <th>预计到期</th>
            <th>事件与权利要求</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td className="mono-cell">{item.family_identifier}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenPatent(item.id)}
                  aria-label={`打开专利族详情：${item.family_identifier}`}
                >
                  {item.title}
                </button>
              </td>
              <td>{item.applicants.join("、") || "--"}</td>
              <td>{formatDate(item.priority_date)}</td>
              <td>
                <StatusBadge value={item.legal_status ?? "unknown"} />
              </td>
              <td>{formatDate(item.expiration_date)}</td>
              <td>
                <PatentTimeline patent={item} />
              </td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "patent_family", resourceId: item.id, label: item.family_identifier }}
                  onOpen={onOpen}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

function Deals({
  items,
  onOpen,
  onOpenDeal,
}: {
  items: Deal[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenDeal: (dealId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联交易" />;
  return (
    <div className="record-list">
      {items.map((item) => (
        <article key={item.id}>
          <div className="record-icon">
            <Building2 size={18} />
          </div>
          <div>
            <span className="record-kicker">
              {item.deal_type} · {formatDate(item.announced_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenDeal(item.id)}
                aria-label={`打开交易详情：${item.parties.map(stringifyParty).join(" × ") || "交易方未记录"}`}
              >
                {item.parties.map(stringifyParty).join(" × ") || "交易方未记录"}
              </button>
            </h3>
            <p>{item.territory ?? "地域条款未记录"}</p>
            <div className="record-meta">
              <span>首付款 {money(item.upfront_amount, item.currency)}</span>
              <span>潜在总额 {money(item.total_potential_amount, item.currency)}</span>
            </div>
          </div>
          <ProvenanceButton
            selection={{ resourceType: "deal", resourceId: item.id, label: `${item.deal_type} 交易` }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}

function RegulatoryEvents({
  items,
  onOpen,
  onOpenRegulatoryEvent,
}: {
  items: RegulatoryEvent[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenRegulatoryEvent: (eventId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联监管事件" />;
  return (
    <ScrollableTableRegion ariaLabel="靶点关联监管事件">
      <table aria-label="靶点关联监管事件">
        <thead>
          <tr>
            <th>监管机构</th>
            <th>事件</th>
            <th>标题</th>
            <th>申请号</th>
            <th>状态</th>
            <th>决定日期</th>
            <th>来源</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{item.agency}</strong>
                <small className="table-secondary">{item.jurisdiction}</small>
              </td>
              <td>{item.event_type.replaceAll("_", " ")}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenRegulatoryEvent(item.id)}
                  aria-label={`打开监管事件详情：${item.title}`}
                >
                  {item.title}
                </button>
              </td>
              <td className="mono-cell">{item.application_number ?? item.event_identifier}</td>
              <td>
                <StatusBadge value={item.status ?? item.event_type} />
              </td>
              <td>{formatDate(item.decision_date)}</td>
              <td className="mono-cell">{item.source_document_id ?? "--"}</td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "regulatory_event", resourceId: item.id, label: item.title }}
                  onOpen={onOpen}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

function NewsEvents({
  items,
  onOpen,
  onOpenNewsEvent,
}: {
  items: TargetNewsEvent[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenNewsEvent: (eventId: string) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联新闻或会议动态" />;
  return (
    <div className="record-list">
      {items.map((item) => (
        <article key={item.id}>
          <div className="record-icon">
            <Newspaper size={18} />
          </div>
          <div>
            <span className="record-kicker">
              {item.event_type} · {formatDate(item.published_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenNewsEvent(item.id)}
                aria-label={`打开新闻事件详情：${item.title}`}
              >
                {item.title}
              </button>
            </h3>
            <p>{item.summary ?? item.venue ?? item.event_identifier}</p>
          </div>
          <ProvenanceButton
            selection={{ resourceType: "news_event", resourceId: item.id, label: item.title }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}

function Structures({
  items,
  onOpen,
}: {
  items: CompoundStructure[];
  onOpen: (selection: ProvenanceSelection) => void;
}) {
  if (!items.length) return <EmptyState title="暂无关联化学结构" />;
  return (
    <div className="structure-grid">
      {items.map((item) => (
        <article key={item.id}>
          <MoleculeDepiction smiles={item.canonical_smiles} name={item.molecular_formula ?? "化合物"} />
          <div>
            <span>{item.molecular_formula ?? "分子式未记录"}</span>
            <strong>{item.standard_inchi_key}</strong>
            <code>{item.canonical_smiles}</code>
            <small>
              MW {item.molecular_weight ?? "--"} · Exact {item.exact_mass ?? "--"}
            </small>
            <small>{item.standardization_version}</small>
            <ProvenanceButton
              selection={{
                resourceType: "compound_structure",
                resourceId: item.id,
                label: item.standard_inchi_key,
              }}
              onOpen={onOpen}
            />
          </div>
        </article>
      ))}
    </div>
  );
}

function money(value: number | null, currency: string | null): string {
  if (value === null) return "--";
  return `${currency ?? ""} ${new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 2 }).format(value)}`.trim();
}
