import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  CalendarDays,
  Clock3,
  Dna,
  ExternalLink,
  FlaskConical,
  Landmark,
  MapPin,
  Pill,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { DossierCoverageDisclosure } from "../components/DossierCoverageDisclosure";
import { MoleculeDepiction } from "../components/MoleculeDepiction";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ResultPagination } from "../components/ResultPagination";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import {
  type DrugDossier,
  drugDossierKeys,
  drugProgramKeys,
  loadDrugDossier,
  loadDrugPrograms,
} from "../lib/contracts/drugDossier";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import {
  statusLabels as dealStatusLabels,
  dealTypeLabels,
  directionLabels,
  formatAmount,
  partyRoleLabels,
  rightTypeLabels,
} from "../lib/dealDisplay";
import type { EntityType } from "../lib/generated";
import { phaseLabel } from "../lib/phasePresentation";
import { programModalityLabel, programTagLabel, publicProgramTags } from "../lib/programDisplay";
import { publicCoverageNotice } from "../lib/publicWarnings";
import type { Entity } from "../lib/types";
import type { DrugDossierSection } from "../lib/workspaceRouting";
import {
  Activities,
  type DossierEntityOpener,
  News,
  Patents,
  Regulatory,
  Relationships,
  Structures,
} from "./EntityDossierView";

const drugTabs: Array<ResearchTabOption<DrugDossierSection>> = [
  { key: "overview", label: "药物概览" },
  { key: "pipeline", label: "研发管线" },
  { key: "relationships", label: "关联信息" },
  { key: "activities", label: "活性" },
  { key: "trials", label: "临床结果与试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易" },
  { key: "regulatory", label: "获批与监管" },
  { key: "news", label: "动态" },
  { key: "structures", label: "结构" },
];

type DrugEntityKind = Extract<EntityType, "target" | "disease" | "organization">;
type DrugEntityOpener = (entityType: EntityType, entityId: string) => void;

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

  if (!drug) return <EmptyState title="尚未选择药物" detail="请从查询或管线结果中打开药物档案" />;
  if (drug.entity_type !== "drug") {
    return <ErrorState message="该深链接不是药物实体，无法打开药物专业档案" />;
  }
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : "药物档案加载失败"}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={`正在加载 ${drug.name} 药物档案`} />;

  const data = dossier.data;
  const programItems = programPage.data?.items ?? (programOffset === 0 ? data.programs : []);
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
            <span>药物专业档案</span>
            <h2>{data.entity.name}</h2>
            <p>{data.entity.description ?? "暂无药物摘要"}</p>
          </div>
        </header>

        <dl className="dossier-metrics drug-profile-metrics">
          <div>
            <dt>最高阶段</dt>
            <dd>{phaseLabel(data.summary.highest_phase)}</dd>
          </div>
          <div>
            <dt>全球 / 中国</dt>
            <dd>
              {phaseLabel(data.summary.highest_global_phase)} / {phaseLabel(data.summary.highest_china_phase)}
            </dd>
          </div>
          <div>
            <dt>研发项目</dt>
            <dd>{data.summary.program_count}</dd>
          </div>
          <div>
            <dt>靶点 / 适应症</dt>
            <dd>
              {data.summary.target_count} / {data.summary.indication_count}
            </dd>
          </div>
          <div>
            <dt>研发机构</dt>
            <dd>{data.summary.organization_count}</dd>
          </div>
          <div>
            <dt>最新状态</dt>
            <dd>{formatDate(data.summary.latest_status_date)}</dd>
          </div>
        </dl>

        <ResearchTabList
          tabs={tabs}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel="药物专业档案视图"
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
              error={programPage.error}
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

type DrugClinicalTrial = DrugDossier["clinical_trials"][number];

const trialPhaseLabels: Record<string, string> = {
  EARLY_PHASE1: "早期 I 期",
  PHASE1: "I 期",
  PHASE1_PHASE2: "I/II 期",
  PHASE2: "II 期",
  PHASE2_PHASE3: "II/III 期",
  PHASE3: "III 期",
  PHASE4: "IV 期",
  NA: "不适用",
};

const trialStatusLabels: Record<string, string> = {
  ACTIVE_NOT_RECRUITING: "进行中，停止招募",
  COMPLETED: "已完成",
  ENROLLING_BY_INVITATION: "邀请入组",
  NOT_YET_RECRUITING: "尚未招募",
  RECRUITING: "招募中",
  SUSPENDED: "已暂停",
  TERMINATED: "已终止",
  UNKNOWN: "未知",
  WITHDRAWN: "已撤回",
};

const trialResultLabels: Record<string, string> = {
  non_inferior: "非劣效",
  not_superior: "未显示优效",
  positive: "积极",
  similar: "相似",
  superior: "优效",
  terminated: "终止",
  unfavorable: "不利",
};

const trialInitiationLabels: Record<string, string> = {
  iit: "研究者发起（IIT）",
  ist: "申办方发起（IST）",
};

const trialStudyTypeLabels: Record<string, string> = {
  EXPANDED_ACCESS: "扩展使用",
  INTERVENTIONAL: "干预性研究",
  OBSERVATIONAL: "观察性研究",
};

const disclosureTypeLabels: Record<string, string> = {
  conference_abstract: "会议摘要",
  conference_presentation: "会议报告",
  journal_article: "期刊论文",
  other: "其他披露",
  poster: "Poster",
  press_release: "新闻稿",
  registry_result: "注册结果",
};

const trialRoleLabels: Record<string, string> = {
  combination_drug: "联用药物",
  combination_target: "联用靶点",
  investigational_drug: "试验药物",
  investigational_target: "试验靶点",
};

function clinicalList(values: string[], empty = "未披露", max = 2) {
  if (!values.length) return empty;
  const visible = values.slice(0, max).join("、");
  return values.length > max ? `${visible} 等 ${values.length} 项` : visible;
}

function clinicalObjectNames(values: Array<{ name: string }>, empty = "未披露", max = 2) {
  return clinicalList(values.map((item) => item.name).filter(Boolean), empty, max);
}

function TrialRoleLinks({
  trial,
  roles,
  onOpenEntity,
}: {
  trial: DrugClinicalTrial;
  roles: string[];
  onOpenEntity: DrugEntityOpener;
}) {
  const items = (trial.entity_roles ?? []).filter((item) => roles.includes(item.role));
  if (!items.length) return <span>未披露</span>;
  return (
    <span className="drug-clinical-role-links">
      {items.map((item) => (
        <button
          type="button"
          key={`${item.role}-${item.entity_id}`}
          aria-label={`打开${trialRoleLabels[item.role] ?? item.role}：${item.name}`}
          onClick={() => onOpenEntity(item.entity_type, item.entity_id)}
        >
          <small>{trialRoleLabels[item.role] ?? item.role}</small>
          {item.name}
        </button>
      ))}
    </span>
  );
}

function TrialOutcomeSummary({ trial }: { trial: DrugClinicalTrial }) {
  const reported = trial.outcomes.filter((outcome) => (outcome.results ?? []).length);
  if (!reported.length) {
    return <span>{trial.has_results ? "结果已发布，结构化终点未披露" : "未发布结果"}</span>;
  }
  const outcomes = [...reported].sort((left, right) => {
    const leftPrimary = left.outcome_type?.toUpperCase() === "PRIMARY" ? 0 : 1;
    const rightPrimary = right.outcome_type?.toUpperCase() === "PRIMARY" ? 0 : 1;
    return leftPrimary - rightPrimary;
  });
  return (
    <span className="drug-clinical-outcomes">
      {outcomes.slice(0, 2).map((outcome) => (
        <span key={`${outcome.outcome_type}-${outcome.measure}-${outcome.time_frame ?? ""}`}>
          <strong>{outcome.measure}</strong>
          <small>
            {(outcome.results ?? [])
              .slice(0, 2)
              .map((result) => `${result.group_label}: ${result.value}${result.unit ? ` ${result.unit}` : ""}`)
              .join("；")}
          </small>
          {outcome.time_frame ? <small>{outcome.time_frame}</small> : null}
        </span>
      ))}
      {outcomes.length > 2 ? <small>另有 {outcomes.length - 2} 项结构化终点</small> : null}
    </span>
  );
}

function TrialActions({
  trial,
  onOpen,
  onOpenTrial,
}: {
  trial: DrugClinicalTrial;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
}) {
  return (
    <div className="row-actions">
      <button
        className="icon-button"
        type="button"
        title="打开临床试验详情"
        aria-label={`打开临床试验详情：${trial.registry_id}`}
        onClick={() => onOpenTrial(trial.id)}
      >
        <ExternalLink size={16} />
      </button>
      <ProvenanceButton
        selection={{ resourceType: "clinical_trial", resourceId: trial.id, label: trial.registry_id }}
        onOpen={onOpen}
      />
    </div>
  );
}

function DrugClinicalEvidence({
  data,
  onOpen,
  onOpenEntity,
  onOpenTrial,
}: {
  data: DrugDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: DrugEntityOpener;
  onOpenTrial: (trialId: string) => void;
}) {
  const resultTrials = data.clinical_trials.filter(
    (trial) =>
      trial.has_results ||
      (trial.key_result_count ?? 0) > 0 ||
      trial.outcomes.some((outcome) => (outcome.results ?? []).length),
  );
  if (!data.clinical_trials.length) return <EmptyState title="暂无关联临床结果或试验" />;

  return (
    <div className="drug-clinical-view">
      <section className="drug-profile-section" aria-labelledby="drug-clinical-results-title">
        <header>
          <div>
            <span>疗效与披露</span>
            <h3 id="drug-clinical-results-title">临床结果（{resultTrials.length}）</h3>
          </div>
          <FlaskConical size={18} aria-hidden="true" />
        </header>
        {resultTrials.length ? (
          <ScrollableTableRegion ariaLabel="药物临床结果" className="drug-clinical-results-region">
            <table aria-label="药物临床结果">
              <thead>
                <tr>
                  <th>试验</th>
                  <th>适应症</th>
                  <th>分期与线次</th>
                  <th>核心疗效</th>
                  <th>总体评价</th>
                  <th>试验/联用药物</th>
                  <th>试验/联用靶点</th>
                  <th>最近披露</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {resultTrials.map((trial) => (
                  <tr key={trial.id}>
                    <td>
                      <button className="table-link-button" type="button" onClick={() => onOpenTrial(trial.id)}>
                        {trial.registry_id}
                      </button>
                      <small className="cell-subtitle">{trial.acronym ?? trial.official_title}</small>
                    </td>
                    <td>{clinicalList(trial.conditions)}</td>
                    <td>
                      {clinicalList(trial.phases.map((phase) => trialPhaseLabels[phase] ?? phase))}
                      <small className="cell-subtitle">
                        {clinicalList(
                          trial.therapy_lines.map((line) => lineOfTherapyLabels[line] ?? line),
                          "线次未披露",
                          3,
                        )}
                      </small>
                    </td>
                    <td>
                      <TrialOutcomeSummary trial={trial} />
                    </td>
                    <td>
                      <StatusBadge
                        value={trial.result_evaluation ?? (trial.has_results ? "reported" : "unreported")}
                        label={
                          trial.result_evaluation
                            ? (trialResultLabels[trial.result_evaluation] ?? trial.result_evaluation)
                            : trial.has_results
                              ? "已披露，未评价"
                              : "未披露"
                        }
                      />
                    </td>
                    <td>
                      <TrialRoleLinks
                        trial={trial}
                        roles={["investigational_drug", "combination_drug"]}
                        onOpenEntity={onOpenEntity}
                      />
                    </td>
                    <td>
                      <TrialRoleLinks
                        trial={trial}
                        roles={["investigational_target", "combination_target"]}
                        onOpenEntity={onOpenEntity}
                      />
                    </td>
                    <td>
                      {trial.latest_result_disclosure ? (
                        <span className="cell-stack">
                          <strong>
                            {disclosureTypeLabels[trial.latest_result_disclosure.disclosure_type] ??
                              trial.latest_result_disclosure.disclosure_type}
                          </strong>
                          <small>{formatDate(trial.latest_result_disclosure.disclosed_at)}</small>
                          {trial.latest_result_disclosure.conference_name ? (
                            <small>{trial.latest_result_disclosure.conference_name}</small>
                          ) : null}
                        </span>
                      ) : (
                        formatDate(trial.results_first_posted)
                      )}
                    </td>
                    <td>
                      <TrialActions trial={trial} onOpen={onOpen} onOpenTrial={onOpenTrial} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title="暂无结构化临床结果" detail="关联试验仍保留在下方试验列表" />
        )}
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-clinical-trials-title">
        <header>
          <div>
            <span>登记与设计</span>
            <h3 id="drug-clinical-trials-title">临床试验（{data.clinical_trials.length}）</h3>
          </div>
          <CalendarDays size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel="药物关联临床试验" className="drug-clinical-trials-region">
          <table aria-label="药物关联临床试验">
            <thead>
              <tr>
                <th>登记号与标题</th>
                <th>状态</th>
                <th>研究类型</th>
                <th>干预方案</th>
                <th>申办方</th>
                <th>入组</th>
                <th>起止日期</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {data.clinical_trials.map((trial) => (
                <tr key={trial.id}>
                  <td>
                    <button className="table-link-button" type="button" onClick={() => onOpenTrial(trial.id)}>
                      {trial.registry_id}
                    </button>
                    <small className="cell-subtitle">{trial.official_title}</small>
                  </td>
                  <td>
                    <StatusBadge
                      value={trial.overall_status ?? "UNKNOWN"}
                      label={trialStatusLabels[trial.overall_status ?? "UNKNOWN"] ?? trial.overall_status ?? "未知"}
                    />
                  </td>
                  <td>
                    {trial.study_type ? (trialStudyTypeLabels[trial.study_type] ?? trial.study_type) : "未披露"}
                    <small className="cell-subtitle">
                      {trial.initiation_type
                        ? (trialInitiationLabels[trial.initiation_type] ?? trial.initiation_type)
                        : "发起类型未披露"}
                    </small>
                  </td>
                  <td>{clinicalObjectNames(trial.interventions, "未披露", 3)}</td>
                  <td>{clinicalObjectNames(trial.sponsors)}</td>
                  <td>{trial.enrollment == null ? "未披露" : trial.enrollment.toLocaleString()}</td>
                  <td>
                    {formatDate(trial.start_date)}
                    <small className="cell-subtitle">至 {formatDate(trial.completion_date)}</small>
                  </td>
                  <td>
                    <TrialActions trial={trial} onOpen={onOpen} onOpenTrial={onOpenTrial} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>
    </div>
  );
}

const approvalEventTypes = new Set(["approval", "conditional_approval"]);

const regulatoryEventLabels: Record<string, string> = {
  acceptance: "受理",
  approval: "批准上市",
  conditional_approval: "附条件批准",
  designation: "资格认定",
  label_update: "标签更新",
  priority_review: "优先审评",
  rejection: "未批准",
  safety_communication: "安全沟通",
  safety_signal: "安全信号",
  submission: "申报",
  suspension: "暂停",
  withdrawal: "撤回",
};

const regulatoryStatusLabels: Record<string, string> = {
  active: "有效",
  approved: "已批准",
  inactive: "失效",
  pending: "待处理",
  rejected: "未批准",
  suspended: "暂停",
  withdrawn: "已撤回",
};

const jurisdictionLabels: Record<string, string> = {
  CN: "中国",
  EU: "欧洲",
  Global: "全球",
  JP: "日本",
  US: "美国",
};

const lineOfTherapyLabels: Record<string, string> = {
  adjuvant: "辅助治疗",
  first_line: "一线",
  maintenance: "维持治疗",
  neoadjuvant: "新辅助治疗",
  second_line: "二线",
  third_line: "三线",
  third_line_or_later: "三线及以上",
  third_or_later: "三线及以上",
};

const routeLabels: Record<string, string> = {
  inhaled: "吸入",
  intramuscular: "肌内注射",
  intravenous: "静脉给药",
  oral: "口服",
  subcutaneous: "皮下注射",
  topical: "局部用药",
};

const dosageFormLabels: Record<string, string> = {
  capsule: "胶囊",
  injection: "注射剂",
  solution: "溶液剂",
  tablet: "片剂",
};

function governedDisplay(value: string, labels: Record<string, string>) {
  return labels[value] ?? value;
}

function DrugRegulatory({
  data,
  onOpen,
  onOpenEntity,
  onOpenRegulatoryEvent,
}: {
  data: DrugDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: DrugEntityOpener;
  onOpenRegulatoryEvent: (eventId: string) => void;
}) {
  const approvals = data.regulatory_events.filter((item) => approvalEventTypes.has(item.event_type));
  const otherEvents = data.regulatory_events.filter((item) => !approvalEventTypes.has(item.event_type));
  if (!data.regulatory_events.length) return <EmptyState title="暂无关联获批或监管事件" />;

  return (
    <div className="drug-regulatory-view">
      <section className="drug-profile-section" aria-labelledby="drug-approvals-title">
        <header>
          <div>
            <span>上市与适应症</span>
            <h3 id="drug-approvals-title">获批适应症（{approvals.length}）</h3>
          </div>
          <Landmark size={18} aria-hidden="true" />
        </header>
        {approvals.length ? (
          <ScrollableTableRegion ariaLabel="药物获批适应症" className="drug-regulatory-table-region">
            <table aria-label="药物获批适应症">
              <thead>
                <tr>
                  <th>适应症</th>
                  <th>获批时间</th>
                  <th>国家/地区</th>
                  <th>审批类型</th>
                  <th>获批人群与限定</th>
                  <th>监管机构</th>
                  <th>状态</th>
                  <th aria-label="操作" />
                </tr>
              </thead>
              <tbody>
                {approvals.map((item) => {
                  const indication = item.indication_entity;
                  const qualifiers = [
                    item.line_of_therapy
                      ? `治疗线次：${governedDisplay(item.line_of_therapy, lineOfTherapyLabels)}`
                      : null,
                    item.biomarker ? `生物标志物：${item.biomarker}` : null,
                    item.dosage_form ? `剂型：${governedDisplay(item.dosage_form, dosageFormLabels)}` : null,
                    item.route_of_administration
                      ? `给药途径：${governedDisplay(item.route_of_administration, routeLabels)}`
                      : null,
                  ].filter(Boolean);
                  return (
                    <tr key={item.id}>
                      <td>
                        {indication ? (
                          <button
                            className="table-link-button"
                            type="button"
                            onClick={() => onOpenEntity(indication.entity_type, indication.id)}
                          >
                            {indication.name}
                          </button>
                        ) : (
                          "未披露"
                        )}
                      </td>
                      <td>{formatDate(item.decision_date)}</td>
                      <td>{item.jurisdiction ? governedDisplay(item.jurisdiction, jurisdictionLabels) : "未披露"}</td>
                      <td>{regulatoryEventLabels[item.event_type] ?? item.event_type}</td>
                      <td className="drug-regulatory-population">
                        <strong>{item.approved_population ?? item.title}</strong>
                        {qualifiers.length ? <small>{qualifiers.join(" · ")}</small> : null}
                      </td>
                      <td>
                        {item.agency}
                        {item.application_number ? (
                          <small className="cell-subtitle">{item.application_number}</small>
                        ) : null}
                      </td>
                      <td>
                        <StatusBadge
                          value={item.status ?? item.event_type}
                          label={
                            regulatoryStatusLabels[item.status ?? ""] ??
                            regulatoryEventLabels[item.event_type] ??
                            item.status ??
                            item.event_type
                          }
                        />
                      </td>
                      <td>
                        <div className="row-actions">
                          <button
                            className="icon-button"
                            type="button"
                            title="打开监管事件详情"
                            aria-label={`打开监管事件详情：${item.title}`}
                            onClick={() => onOpenRegulatoryEvent(item.id)}
                          >
                            <ExternalLink size={16} />
                          </button>
                          <ProvenanceButton
                            selection={{ resourceType: "regulatory_event", resourceId: item.id, label: item.title }}
                            onOpen={onOpen}
                          />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title="暂无已批准适应症" detail="其他监管事件仍保留在下方时间线" />
        )}
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-other-regulatory-title">
        <header>
          <div>
            <span>申报、标签与安全</span>
            <h3 id="drug-other-regulatory-title">其他监管事件（{otherEvents.length}）</h3>
          </div>
          <ShieldCheck size={18} aria-hidden="true" />
        </header>
        {otherEvents.length ? (
          <Regulatory
            data={{ ...data, regulatory_events: otherEvents }}
            onOpen={onOpen}
            onOpenRegulatoryEvent={onOpenRegulatoryEvent}
          />
        ) : (
          <EmptyState title="暂无其他监管事件" />
        )}
      </section>
    </div>
  );
}

function DrugOverview({
  data,
  onOpenEntity,
  onOpenSection,
}: {
  data: DrugDossier;
  onOpenEntity: DrugEntityOpener;
  onOpenSection: (section: DrugDossierSection) => void;
}) {
  const targets = uniqueProgramEntities(data, "target");
  const indications = uniqueProgramEntities(data, "disease");
  const organizations = uniqueProgramEntities(data, "organization");
  const milestones = data.programs
    .flatMap((program) =>
      (program.milestones ?? []).map((milestone) => ({
        ...milestone,
        programId: program.id,
        drugName: program.drug_name,
      })),
    )
    .sort((left, right) => right.occurred_at.localeCompare(left.occurred_at))
    .slice(0, 5);
  const structure = data.structures[0];
  const coverageNotice = publicCoverageNotice(data.warnings);

  return (
    <div className="drug-profile-overview">
      <section className="drug-profile-section drug-profile-development">
        <header>
          <div>
            <span>研发状态</span>
            <h3>项目、靶点与适应症</h3>
          </div>
          <button type="button" onClick={() => onOpenSection("pipeline")} disabled={!data.programs.length}>
            查看全部管线
          </button>
        </header>
        <dl className="drug-profile-attribute-strip">
          <div>
            <dt>
              <Activity size={15} /> 药物类型
            </dt>
            <dd>{data.summary.modalities.map(programModalityLabel).join("、") || "未披露"}</dd>
          </div>
          <div>
            <dt>
              <Dna size={15} /> 靶点
            </dt>
            <dd>{renderEntityLinks(targets, onOpenEntity)}</dd>
          </div>
          <div>
            <dt>
              <MapPin size={15} /> 适应症
            </dt>
            <dd>{renderEntityLinks(indications, onOpenEntity)}</dd>
          </div>
          <div>
            <dt>
              <Building2 size={15} /> 研发机构
            </dt>
            <dd>{renderEntityLinks(organizations, onOpenEntity)}</dd>
          </div>
        </dl>
      </section>

      <div className="drug-profile-overview-grid">
        <section className="drug-profile-section drug-profile-structure">
          <header>
            <div>
              <span>化学结构</span>
              <h3>主要结构</h3>
            </div>
            <button type="button" onClick={() => onOpenSection("structures")} disabled={!structure}>
              查看结构
            </button>
          </header>
          {structure ? (
            <div className="drug-profile-structure-content">
              <MoleculeDepiction smiles={structure.canonical_smiles} name={data.entity.name} />
              <dl>
                <div>
                  <dt>InChIKey</dt>
                  <dd className="mono-cell">{structure.standard_inchi_key}</dd>
                </div>
                <div>
                  <dt>分子式</dt>
                  <dd>{structure.molecular_formula ?? "未披露"}</dd>
                </div>
                <div>
                  <dt>分子量</dt>
                  <dd>{structure.molecular_weight ?? "未披露"}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <EmptyState title="暂无结构数据" detail="当前数据中未收录可展示的化学结构" />
          )}
        </section>

        <section className="drug-profile-section drug-profile-milestones">
          <header>
            <div>
              <span>变化时间线</span>
              <h3>最近研发里程碑</h3>
            </div>
            <Clock3 size={18} />
          </header>
          {milestones.length ? (
            <ol>
              {milestones.map((milestone) => (
                <li key={`${milestone.programId}-${milestone.milestone_type}-${milestone.occurred_at}`}>
                  <time>{formatDate(milestone.occurred_at)}</time>
                  <div>
                    <strong>{milestone.title}</strong>
                    <span>
                      {milestone.geography ?? "地区未披露"} · {milestone.milestone_type}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title="暂无带日期的研发里程碑" />
          )}
        </section>
      </div>

      <DossierCoverageDisclosure
        available={publicDrugCoverage(data).filter((item) => item.total > 0).length}
        total={data.coverage.length}
      >
        <section className="drug-profile-section drug-profile-coverage">
          <header>
            <div>
              <span>数据概览</span>
              <h3>各类信息收录情况</h3>
            </div>
            <time dateTime={data.as_of} title="本次档案查询时间，不代表所有来源的最后更新时间">
              查询时间 {formatDate(data.as_of, true)}
            </time>
          </header>
          <ScrollableTableRegion ariaLabel="药物档案领域数据覆盖">
            <table aria-label="药物档案领域数据覆盖">
              <thead>
                <tr>
                  <th>信息类型</th>
                  <th>收录数量</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {publicDrugCoverage(data).map((item) => (
                  <tr key={item.domain}>
                    <td>{coverageLabel(item.domain)}</td>
                    <td>{item.total}</td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          {coverageNotice ? (
            <p className="inline-alert">
              <ShieldCheck size={15} /> {coverageNotice}
            </p>
          ) : null}
        </section>
      </DossierCoverageDisclosure>
    </div>
  );
}

type EntityLink = { id: string; name: string; kind: DrugEntityKind };

type DrugCoverageDomain = DrugDossier["coverage"][number]["domain"];

function dossierSectionAvailability(data: DrugDossier, domain: DrugCoverageDomain, observedCount: number) {
  const coverage = data.coverage.find((item) => item.domain === domain);
  const count = Math.max(observedCount, coverage?.total ?? 0);
  return {
    count,
    disabled: count === 0 && coverage?.status === "not_observed",
    disabledReason: count === 0 && coverage?.status === "not_observed" ? "当前数据暂未收录相关信息" : undefined,
  };
}

function drugAssociationCount(data: DrugDossier): number {
  const identities = new Set<string>();
  for (const kind of ["target", "disease", "organization"] as const) {
    for (const entity of uniqueProgramEntities(data, kind)) identities.add(`${entity.kind}:${entity.id}`);
  }
  for (const relationship of data.relationships) {
    identities.add(`${relationship.related_entity.entity_type}:${relationship.related_entity.id}`);
  }
  return identities.size;
}

function publicDrugCoverage(data: DrugDossier): DrugDossier["coverage"] {
  const associationCount = drugAssociationCount(data);
  return data.coverage.map((item) =>
    item.domain === "relationships" && associationCount > item.total
      ? {
          ...item,
          total: associationCount,
          returned: Math.max(item.returned, associationCount),
          status: "available",
          note: "包含研发项目中的靶点、适应症与研发机构",
        }
      : item,
  );
}

function buildDrugTabs(data: DrugDossier, programTotal: number): Array<ResearchTabOption<DrugDossierSection>> {
  const availability: Partial<Record<DrugDossierSection, ReturnType<typeof dossierSectionAvailability>>> = {
    pipeline: dossierSectionAvailability(data, "programs", programTotal),
    relationships: dossierSectionAvailability(data, "relationships", drugAssociationCount(data)),
    activities: dossierSectionAvailability(data, "activities", data.activities.length),
    trials: dossierSectionAvailability(data, "clinical_trials", data.clinical_trials.length),
    patents: dossierSectionAvailability(data, "patents", data.patents.length),
    deals: dossierSectionAvailability(data, "deals", data.deals.length),
    regulatory: dossierSectionAvailability(data, "regulatory_events", data.regulatory_events.length),
    news: dossierSectionAvailability(data, "news_events", data.news_events.length),
    structures: dossierSectionAvailability(data, "structures", data.structures.length),
  };
  return drugTabs.map((tab) => ({ ...tab, ...availability[tab.key] }));
}

function uniqueProgramEntities(data: DrugDossier, kind: "target" | "disease" | "organization"): EntityLink[] {
  const values: EntityLink[] = [];
  for (const program of data.programs) {
    if (kind === "target") {
      const programTargets = program.targets ?? [];
      const targets = programTargets.length
        ? programTargets.map((target) => ({ id: target.entity_id, name: target.name }))
        : program.target_entity_id && program.target_name
          ? [{ id: program.target_entity_id, name: program.target_name }]
          : [];
      values.push(...targets.map((item) => ({ ...item, kind })));
    } else if (kind === "disease") {
      const indicationCount = values.length;
      for (const indication of program.indications ?? []) {
        if (indication.disease_entity_id && indication.disease_name) {
          values.push({ id: indication.disease_entity_id, name: indication.disease_name, kind });
        }
      }
      if (values.length === indicationCount && program.disease_entity_id && program.disease_name) {
        values.push({ id: program.disease_entity_id, name: program.disease_name, kind });
      }
    } else if (kind === "organization") {
      values.push(
        ...programOrganizations(program).map((organization) => ({
          id: organization.entity_id,
          name: organization.name,
          kind,
        })),
      );
    }
  }
  return Array.from(new Map(values.map((item) => [item.id, item])).values()).sort((left, right) =>
    left.name.localeCompare(right.name),
  );
}

function DrugAssociations({
  data,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  data: DrugDossier;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DrugEntityOpener;
}) {
  const targets = uniqueProgramEntities(data, "target");
  const indications = uniqueProgramEntities(data, "disease");
  const organizations = uniqueProgramEntities(data, "organization");
  const hasProgramAssociations = targets.length + indications.length + organizations.length > 0;
  if (!hasProgramAssociations && !data.relationships.length) {
    return <EmptyState title="暂无关联信息" detail="当前数据中未收录该药物的靶点、适应症或研发机构" />;
  }
  return (
    <div className="drug-relationships-view">
      {hasProgramAssociations ? (
        <section className="drug-profile-section" aria-labelledby="drug-associations-title">
          <header>
            <div>
              <span>研发关联</span>
              <h3 id="drug-associations-title">靶点、适应症与研发机构</h3>
            </div>
            <Dna size={18} aria-hidden="true" />
          </header>
          <dl className="drug-profile-attribute-strip">
            <div>
              <dt>作用靶点</dt>
              <dd>{renderEntityLinks(targets, onOpenTypedEntity)}</dd>
            </div>
            <div>
              <dt>适应症</dt>
              <dd>{renderEntityLinks(indications, onOpenTypedEntity)}</dd>
            </div>
            <div>
              <dt>研发机构</dt>
              <dd>{renderEntityLinks(organizations, onOpenTypedEntity)}</dd>
            </div>
          </dl>
        </section>
      ) : null}
      {data.relationships.length ? (
        <section className="drug-profile-section" aria-labelledby="drug-other-relationships-title">
          <header>
            <div>
              <span>其他关联</span>
              <h3 id="drug-other-relationships-title">其他关联记录</h3>
            </div>
          </header>
          <Relationships data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={onOpenTypedEntity} />
        </section>
      ) : null}
    </div>
  );
}

function renderEntityLinks(items: EntityLink[], onOpenEntity: DrugEntityOpener) {
  if (!items.length) return "未披露";
  return items.map((item, index) => (
    <span key={item.id}>
      {index > 0 ? "、" : ""}
      <button className="inline-link-button" type="button" onClick={() => onOpenEntity(item.kind, item.id)}>
        {item.name}
      </button>
    </span>
  ));
}

type DrugProgram = DrugDossier["programs"][number];

const programStatusLabels: Record<string, string> = {
  active: "在研",
  inactive: "非活跃",
  unknown: "状态未知",
};

const organizationRoleLabels: Record<string, string> = {
  originator: "原研",
  collaborator: "合作研发",
  licensee: "被许可方",
  licensor: "许可方",
  manufacturer: "生产方",
  other: "其他",
};

const geographyLabels: Record<string, string> = {
  CN: "中国",
  China: "中国",
  china: "中国",
  EU: "欧洲",
  Europe: "欧洲",
  europe: "欧洲",
  Global: "全球",
  global: "全球",
  "Greater China": "大中华区",
  JP: "日本",
  Japan: "日本",
  japan: "日本",
  US: "美国",
  us: "美国",
};

const innovationTypeLabels: Record<string, string> = {
  best_in_class: "Best-in-Class",
  first_in_class: "First-in-Class",
  me_better: "Me-better",
  me_too: "Me-too",
};

const drugCategoryLabels: Record<string, string> = {
  biologic: "生物制品",
  chemical_drug: "化学药",
  gene_therapy: "基因治疗",
  traditional_medicine: "中药",
};

function geographyLabel(value: string | null | undefined): string {
  return value ? (geographyLabels[value] ?? value) : "未披露";
}

function listValues(values: string[] | null | undefined, empty = "未披露"): string {
  if (!values?.length) return empty;
  return Array.from(new Set(values)).join("、");
}

function listRegions(values: string[] | null | undefined): string {
  return listValues(values?.map((value) => geographyLabel(value)));
}

function governedValue(value: string | null | undefined, labels: Record<string, string>): string | null {
  return value ? (labels[value] ?? value) : null;
}

function programOrganizations(program: DrugProgram): NonNullable<DrugProgram["organizations"]> {
  if (program.organizations?.length) return program.organizations;
  if (!program.organization_entity_id || !program.organization_name) return [];
  return [
    {
      entity_id: program.organization_entity_id,
      name: program.organization_name,
      role: "other" as const,
      position: 0,
    },
  ];
}

function ProgramOrganizationLinks({ program, onOpenEntity }: { program: DrugProgram; onOpenEntity: DrugEntityOpener }) {
  const organizations = programOrganizations(program);
  if (!organizations.length) return <span>未披露</span>;
  return (
    <span className="drug-program-entity-list">
      {organizations.map((organization) => (
        <span key={`${program.id}-${organization.entity_id}-${organization.role}`}>
          <button
            className="table-link-button"
            type="button"
            onClick={() => onOpenEntity("organization", organization.entity_id)}
          >
            {organization.name}
          </button>
          <small>
            {organizationRoleLabels[organization.role] ?? organization.role}
            {organization.country_region ? ` · ${geographyLabel(organization.country_region)}` : ""}
            {organization.organization_type ? ` · ${organization.organization_type}` : ""}
          </small>
        </span>
      ))}
    </span>
  );
}

function ProgramTargetLinks({ program, onOpenEntity }: { program: DrugProgram; onOpenEntity: DrugEntityOpener }) {
  const targets = program.targets?.length
    ? program.targets
    : program.target_entity_id && program.target_name
      ? [{ entity_id: program.target_entity_id, name: program.target_name, role: "primary", position: 0 }]
      : [];
  if (!targets.length) return <span>未披露</span>;
  return (
    <span className="drug-program-targets">
      {targets.map((target) => (
        <button
          className="table-link-button"
          type="button"
          key={`${program.id}-${target.entity_id}-${target.role}`}
          onClick={() => onOpenEntity("target", target.entity_id)}
        >
          {target.name}
        </button>
      ))}
    </span>
  );
}

function ProgramProgressHistory({ program }: { program: DrugProgram }) {
  const events = [
    ...(program.status_history ?? []).map((event) => ({
      date: event.effective_at,
      geography: event.geography,
      key: `status-${event.phase}-${event.effective_at}-${event.geography ?? "global"}`,
      label: `${phaseLabel(event.phase)}${event.status ? ` · ${programStatusLabels[event.status] ?? event.status}` : ""}`,
      detail: event.reason,
    })),
    ...(program.milestones ?? []).map((event) => ({
      date: event.occurred_at,
      geography: event.geography,
      key: `milestone-${event.milestone_type}-${event.occurred_at}-${event.title}`,
      label: event.title,
      detail: event.description,
    })),
  ].sort((left, right) => right.date.localeCompare(left.date));
  if (!events.length) return <span>暂无带日期的进度</span>;
  return (
    <details className="program-history">
      <summary>{events.length} 条阶段与里程碑</summary>
      <ol>
        {events.map((event) => (
          <li key={event.key}>
            <strong>{event.label}</strong> · {formatDate(event.date)} · {geographyLabel(event.geography)}
            {event.detail ? <small>{event.detail}</small> : null}
          </li>
        ))}
      </ol>
    </details>
  );
}

function DrugDevelopmentPortfolio({
  data,
  programs,
  totalPrograms,
  offset,
  pageSize,
  loading,
  fetching,
  error,
  onRetry,
  onPageChange,
  onOpen,
  onOpenEntity,
}: {
  data: DrugDossier;
  programs: DrugDossier["programs"];
  totalPrograms: number;
  offset: number;
  pageSize: number;
  loading: boolean;
  fetching: boolean;
  error: unknown;
  onRetry: () => void;
  onPageChange: (offset: number) => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: DrugEntityOpener;
}) {
  const errorMessage = error instanceof Error ? error.message : "研发管线分页加载失败";
  if (loading && !programs.length) return <Spinner label="正在加载完整研发管线" />;
  if (error && !programs.length) return <ErrorState message={errorMessage} retry={onRetry} />;
  if (!programs.length) return <EmptyState title="暂无关联研发管线" />;
  return (
    <div className="drug-development-view">
      {error ? (
        <p className="domain-pagination-error" role="alert">
          完整研发管线分页加载失败，当前显示已加载内容。
          <button className="text-button" type="button" onClick={onRetry}>
            重试
          </button>
        </p>
      ) : null}
      <section className="drug-profile-section" aria-labelledby="drug-indication-progress-title">
        <header>
          <div>
            <span>适应症与地域</span>
            <h3 id="drug-indication-progress-title">适应症与地区进度（{totalPrograms}）</h3>
          </div>
          <MapPin size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel="药物适应症与地区进度" className="drug-program-progress-region">
          <table aria-label="药物适应症与地区进度">
            <thead>
              <tr>
                <th>适应症</th>
                <th>全球阶段</th>
                <th>中国阶段</th>
                <th>记录地区</th>
                <th>项目状态</th>
                <th>靶点与机制</th>
                <th>最新更新</th>
                <th aria-label="来源" />
              </tr>
            </thead>
            <tbody>
              {programs.map((program) => (
                <tr key={program.id}>
                  <td>
                    {program.disease_entity_id && program.disease_name ? (
                      <button
                        className="table-link-button"
                        type="button"
                        onClick={() => {
                          if (program.disease_entity_id) onOpenEntity("disease", program.disease_entity_id);
                        }}
                      >
                        {program.disease_name}
                      </button>
                    ) : (
                      "未披露"
                    )}
                    {program.therapeutic_area ? (
                      <small className="cell-subtitle">{program.therapeutic_area}</small>
                    ) : null}
                  </td>
                  <td>
                    <strong>{phaseLabel(program.global_phase)}</strong>
                    <small className="cell-subtitle">
                      {program.global_phase_started_at
                        ? `始于 ${formatDate(program.global_phase_started_at)}`
                        : "起始日未披露"}
                    </small>
                  </td>
                  <td>
                    <strong>{phaseLabel(program.china_phase)}</strong>
                    <small className="cell-subtitle">
                      {program.china_phase_started_at
                        ? `始于 ${formatDate(program.china_phase_started_at)}`
                        : "起始日未披露"}
                    </small>
                  </td>
                  <td>{geographyLabel(program.geography)}</td>
                  <td>
                    <StatusBadge
                      value={program.program_status ?? "unknown"}
                      label={programStatusLabels[program.program_status ?? "unknown"]}
                    />
                    {program.status_detail ? <small className="cell-subtitle">{program.status_detail}</small> : null}
                  </td>
                  <td>
                    <ProgramTargetLinks program={program} onOpenEntity={onOpenEntity} />
                    <small className="cell-subtitle">{program.mechanism_of_action ?? "机制未披露"}</small>
                  </td>
                  <td>{formatDate(program.status_date)}</td>
                  <td>
                    <ProvenanceButton
                      selection={{
                        resourceType: "development_program",
                        resourceId: program.id,
                        label: program.disease_name ?? data.entity.name,
                      }}
                      onOpen={onOpen}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-organization-rights-title">
        <header>
          <div>
            <span>开发与商业化</span>
            <h3 id="drug-organization-rights-title">研发机构与权益（{totalPrograms}）</h3>
          </div>
          <Building2 size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel="药物研发机构与权益" className="drug-program-rights-region">
          <table aria-label="药物研发机构与权益">
            <thead>
              <tr>
                <th>适应症</th>
                <th>研发机构与角色</th>
                <th>研发权益</th>
                <th>商业化权益</th>
                <th>药物类型与分类</th>
                <th>项目标签</th>
                <th>阶段历史与里程碑</th>
                <th aria-label="来源" />
              </tr>
            </thead>
            <tbody>
              {programs.map((program) => (
                <tr key={program.id}>
                  <td>{program.disease_name ?? "未披露"}</td>
                  <td>
                    <ProgramOrganizationLinks program={program} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>{listRegions(program.development_rights_regions)}</td>
                  <td>{listRegions(program.commercialization_rights_regions)}</td>
                  <td>
                    {program.modality ? programModalityLabel(program.modality) : "未披露"}
                    <small className="cell-subtitle">
                      {listValues(
                        [
                          governedValue(program.innovation_type, innovationTypeLabels),
                          governedValue(program.drug_category, drugCategoryLabels),
                        ].filter((value): value is string => Boolean(value)),
                      )}
                    </small>
                  </td>
                  <td>{listValues(publicProgramTags(program.program_tags).map(programTagLabel))}</td>
                  <td>
                    <ProgramProgressHistory program={program} />
                  </td>
                  <td>
                    <ProvenanceButton
                      selection={{
                        resourceType: "development_program",
                        resourceId: program.id,
                        label: program.disease_name ?? data.entity.name,
                      }}
                      onOpen={onOpen}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>
      <ResultPagination
        totalRows={totalPrograms}
        offset={offset}
        pageSize={pageSize}
        onPageChange={onPageChange}
        notice={fetching ? "正在更新研发管线…" : undefined}
        ariaLabel="药物研发管线分页"
      />
    </div>
  );
}

type DrugDeal = DrugDossier["deals"][number];

function DrugDealParties({ deal, onOpenEntity }: { deal: DrugDeal; onOpenEntity: DossierEntityOpener }) {
  if (!deal.party_roles.length && !deal.party_entities.length) return <span>参与方未披露</span>;
  return (
    <span className="drug-deal-entity-list">
      {deal.party_roles.length
        ? deal.party_roles.map((party) => (
            <span key={`${deal.id}-${party.id}-${party.role}`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(party.entity_type, party.id)}
              >
                {party.name}
              </button>
              <small>
                {partyRoleLabels[party.role] ?? party.role}
                {party.country_region ? ` · ${geographyLabel(party.country_region)}` : ""}
                {party.organization_type ? ` · ${party.organization_type}` : ""}
              </small>
            </span>
          ))
        : deal.party_entities.map((party) => (
            <span key={`${deal.id}-${party.id}-undisclosed`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(party.entity_type, party.id)}
              >
                {party.name}
              </button>
              <small>角色未披露</small>
            </span>
          ))}
    </span>
  );
}

function DrugDealAssets({ deal, onOpenEntity }: { deal: DrugDeal; onOpenEntity: DossierEntityOpener }) {
  if (!deal.asset_stages.length && !deal.asset_entities.length) return <span>交易资产未披露</span>;
  return (
    <span className="drug-deal-entity-list">
      {deal.asset_stages.length
        ? deal.asset_stages.map((asset) => (
            <span key={`${deal.id}-${asset.id}`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(asset.entity_type, asset.id)}
              >
                {asset.name}
              </button>
              <small>
                交易时 {phaseLabel(asset.development_phase_at_transaction)}
                {asset.current_development_phase ? ` · 当前 ${phaseLabel(asset.current_development_phase)}` : ""}
                {asset.current_phase_as_of ? ` · ${formatDate(asset.current_phase_as_of)}` : ""}
              </small>
            </span>
          ))
        : deal.asset_entities.map((asset) => (
            <span key={`${deal.id}-${asset.id}`}>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenEntity(asset.entity_type, asset.id)}
              >
                {asset.name}
              </button>
              <small>交易时阶段未披露</small>
            </span>
          ))}
    </span>
  );
}

function DrugDealActions({
  deal,
  onOpen,
  onOpenDeal,
}: {
  deal: DrugDeal;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenDeal: (dealId: string) => void;
}) {
  return (
    <div className="row-actions">
      <button
        className="icon-button"
        type="button"
        title="打开交易详情"
        aria-label={`打开交易详情：${deal.name}`}
        onClick={() => onOpenDeal(deal.id)}
      >
        <ExternalLink size={16} />
      </button>
      <ProvenanceButton selection={{ resourceType: "deal", resourceId: deal.id, label: deal.name }} onOpen={onOpen} />
    </div>
  );
}

function DrugDealIntelligence({
  data,
  onOpen,
  onOpenDeal,
  onOpenEntity,
}: {
  data: DrugDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenDeal: (dealId: string) => void;
  onOpenEntity: DossierEntityOpener;
}) {
  if (!data.deals.length) return <EmptyState title="暂无关联交易" />;
  const rights = data.deals.flatMap((deal) => deal.rights.map((right) => ({ deal, right })));
  return (
    <div className="drug-deal-view">
      <section className="drug-profile-section" aria-labelledby="drug-linked-deals-title">
        <header>
          <div>
            <span>交易与资产</span>
            <h3 id="drug-linked-deals-title">关联交易（{data.deals.length}）</h3>
          </div>
          <Landmark size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel="药物关联交易" className="drug-deal-table-region">
          <table aria-label="药物关联交易">
            <thead>
              <tr>
                <th>交易与披露</th>
                <th>状态与方向</th>
                <th>参与方与角色</th>
                <th>资产与阶段</th>
                <th>披露金额</th>
                <th>地域与权益</th>
                <th>信息更新</th>
                <th aria-label="操作" />
              </tr>
            </thead>
            <tbody>
              {data.deals.map((deal) => (
                <tr key={deal.id}>
                  <td>
                    <button className="table-link-button" type="button" onClick={() => onOpenDeal(deal.id)}>
                      {deal.name}
                    </button>
                    <small className="cell-subtitle">
                      {dealTypeLabels[deal.deal_type] ?? deal.deal_type} · {formatDate(deal.announced_at)}
                    </small>
                  </td>
                  <td>
                    <StatusBadge value={deal.status} label={dealStatusLabels[deal.status] ?? deal.status} />
                    <small className="cell-subtitle">{directionLabels[deal.direction] ?? deal.direction}</small>
                  </td>
                  <td>
                    <DrugDealParties deal={deal} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>
                    <DrugDealAssets deal={deal} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>
                    <span className="cell-stack">
                      <strong>首付款 {formatAmount(deal.upfront_amount, deal.currency)}</strong>
                      <small>潜在总额 {formatAmount(deal.total_potential_amount, deal.currency)}</small>
                    </span>
                  </td>
                  <td>
                    {deal.territory ? geographyLabel(deal.territory) : "交易地域未披露"}
                    <small className="cell-subtitle">{deal.rights.length} 条结构化权益</small>
                  </td>
                  <td>{formatDate(deal.source_updated_at)}</td>
                  <td>
                    <DrugDealActions deal={deal} onOpen={onOpen} onOpenDeal={onOpenDeal} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-deal-rights-title">
        <header>
          <div>
            <span>持有人与地域</span>
            <h3 id="drug-deal-rights-title">权益归属（{rights.length}）</h3>
          </div>
          <ShieldCheck size={18} aria-hidden="true" />
        </header>
        {rights.length ? (
          <ScrollableTableRegion ariaLabel="药物交易权益归属" className="drug-deal-rights-region">
            <table aria-label="药物交易权益归属">
              <thead>
                <tr>
                  <th>权益持有人</th>
                  <th>权益类型</th>
                  <th>权益地区</th>
                  <th>独占性</th>
                  <th>范围说明</th>
                  <th>关联交易</th>
                  <th aria-label="来源" />
                </tr>
              </thead>
              <tbody>
                {rights.map(({ deal, right }) => (
                  <tr key={`${deal.id}-${right.id}`}>
                    <td>
                      <button
                        className="table-link-button"
                        type="button"
                        onClick={() => onOpenEntity("organization", right.holder_entity_id)}
                      >
                        {right.holder_name}
                      </button>
                    </td>
                    <td>{rightTypeLabels[right.right_type] ?? right.right_type}</td>
                    <td>{geographyLabel(right.territory)}</td>
                    <td>{right.exclusive == null ? "未披露" : right.exclusive ? "独占" : "非独占"}</td>
                    <td>{right.scope_description ?? "范围说明未披露"}</td>
                    <td>
                      <button className="table-link-button" type="button" onClick={() => onOpenDeal(deal.id)}>
                        {deal.name}
                      </button>
                    </td>
                    <td>
                      <ProvenanceButton
                        selection={{ resourceType: "deal", resourceId: deal.id, label: deal.name }}
                        onOpen={onOpen}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
        ) : (
          <EmptyState title="当前关联交易未披露结构化地域权益" />
        )}
      </section>
    </div>
  );
}

function coverageLabel(value: string): string {
  const labels: Record<string, string> = {
    relationships: "关联信息",
    evidence: "资料来源",
    activities: "生物活性",
    programs: "研发项目",
    clinical_trials: "临床试验",
    patents: "专利信息",
    deals: "交易信息",
    regulatory_events: "监管信息",
    news_events: "新闻与会议",
    structures: "化学结构",
    target_evidence: "靶点证据",
  };
  return labels[value] ?? value;
}
