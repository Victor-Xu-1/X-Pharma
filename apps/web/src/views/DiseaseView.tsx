import { useQuery } from "@tanstack/react-query";
import { Activity, Dna, ShieldCheck, Stethoscope } from "lucide-react";
import { useState } from "react";

import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { DossierCoverageDisclosure } from "../components/DossierCoverageDisclosure";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import { type DiseaseDossier, diseaseKeys, loadDiseaseDossier } from "../lib/contracts/disease";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import type { EpidemiologyObservationSearchItemRead } from "../lib/generated";
import type { Entity } from "../lib/types";
import type { DiseaseDossierSection } from "../lib/workspaceRouting";
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

const tabs: Array<ResearchTabOption<DiseaseDossierSection>> = [
  { key: "overview", label: "疾病概览" },
  { key: "epidemiology", label: "流行病学" },
  { key: "pipeline", label: "研发格局" },
  { key: "evidence", label: "靶点证据" },
  { key: "trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易合作" },
  { key: "regulatory", label: "监管" },
  { key: "news", label: "疾病动态" },
  { key: "relationships", label: "关联网络" },
];

const phaseLabels: Record<string, string> = {
  discontinued: "已终止",
  discovery: "发现阶段",
  preclinical: "临床前",
  ind: "IND",
  phase_1: "I 期临床",
  phase_1_2: "I/II 期临床",
  phase_2: "II 期临床",
  phase_2_3: "II/III 期临床",
  phase_3: "III 期临床",
  filed: "已申报",
  approved: "已批准",
};

const measureLabels: Record<string, string> = {
  prevalence: "患病率",
  incidence: "发病率",
  mortality: "死亡率",
  patient_count: "患者人数",
  diagnosed_count: "诊断人数",
  treated_count: "治疗人数",
  survival_rate: "生存率",
  daly: "伤残调整生命年",
  other: "其他",
};

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
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const dossier = useQuery({
    queryKey: diseaseKeys.dossier(disease?.id ?? ""),
    queryFn: ({ signal }) => loadDiseaseDossier(disease?.id ?? "", signal),
    enabled: Boolean(disease?.id && disease.entity_type === "disease"),
  });

  if (!disease) return <EmptyState title="尚未选择疾病" detail="请从查询、管线或流行病学结果中打开疾病档案" />;
  if (disease.entity_type !== "disease") {
    return <ErrorState message="该深链接不是疾病实体，无法打开疾病专业档案" />;
  }
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : "疾病档案加载失败"}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={`正在加载 ${disease.name} 疾病档案`} />;

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
      <section className="company-profile-page disease-profile-page">
        <header className="company-profile-header disease-profile-header">
          <div className="company-profile-symbol disease-profile-symbol">
            <Stethoscope size={23} />
          </div>
          <div className="company-profile-identity">
            <span>疾病专业档案</span>
            <h2>{data.entity.name}</h2>
            <p>{data.entity.description ?? "暂无疾病简介"}</p>
          </div>
        </header>

        <dl className="dossier-metrics company-profile-metrics">
          <div>
            <dt>最高研发阶段</dt>
            <dd>{phaseLabel(data.summary.highest_phase)}</dd>
          </div>
          <div>
            <dt>研发项目 / 药物</dt>
            <dd>
              {data.summary.program_count} / {data.summary.drug_count}
            </dd>
          </div>
          <div>
            <dt>靶点 / 公司</dt>
            <dd>
              {data.summary.target_count} / {data.summary.organization_count}
            </dd>
          </div>
          <div>
            <dt>疾病负担观测</dt>
            <dd>{data.summary.epidemiology_observation_count}</dd>
          </div>
          <div>
            <dt>临床试验 / 专利</dt>
            <dd>
              {data.summary.clinical_trial_count} / {data.summary.patent_count}
            </dd>
          </div>
          <div>
            <dt>最近活动</dt>
            <dd>{formatDate(data.summary.latest_activity_at)}</dd>
          </div>
        </dl>

        <ResearchTabList
          tabs={tabs}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel="疾病专业档案视图"
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
      {provenanceSelection ? (
        <RecordProvenanceDrawer selection={provenanceSelection} onClose={() => setProvenanceSelection(null)} />
      ) : null}
    </>
  );
}

function DiseaseOverview({
  data,
  onOpenTypedEntity,
  onOpenSection,
  onOpenEpidemiology,
}: {
  data: DiseaseDossier;
  onOpenTypedEntity: DossierEntityOpener;
  onOpenSection: (section: DiseaseDossierSection) => void;
  onOpenEpidemiology: (diseaseId: string) => void;
}) {
  const phaseDistribution = data.summary.phase_distribution ?? {};
  const maximumPhaseCount = Math.max(1, ...Object.values(phaseDistribution));
  const targets = Array.from(
    new Map([
      ...data.programs.flatMap((program) =>
        (program.targets?.length
          ? program.targets
          : [{ entity_id: program.target_entity_id, name: program.target_name }]
        )
          .filter((target) => target.entity_id && target.name)
          .map((target) => [target.entity_id as string, target.name as string] as const),
      ),
      ...data.target_evidence.map((item) => [item.target_entity_id, item.target_name] as const),
    ]).entries(),
  );

  return (
    <div className="company-profile-overview disease-profile-overview">
      <div className="company-profile-overview-grid">
        <section className="company-profile-section">
          <header>
            <div>
              <span>DEVELOPMENT LANDSCAPE</span>
              <h3>研发阶段分布</h3>
            </div>
            <button type="button" onClick={() => onOpenSection("pipeline")} disabled={!data.programs.length}>
              查看研发格局
            </button>
          </header>
          {Object.keys(phaseDistribution).length ? (
            <ol className="company-phase-distribution" aria-label="疾病研发阶段分布">
              {Object.entries(phaseDistribution).map(([phase, count]) => (
                <li key={phase}>
                  <span>{phaseLabel(phase)}</span>
                  <div>
                    <i style={{ width: `${(count / maximumPhaseCount) * 100}%` }} />
                  </div>
                  <strong>{count}</strong>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title="暂无可统计研发阶段" />
          )}
          <p className="company-modality-line">
            <Activity size={15} />
            {(data.summary.modalities ?? []).join("、") || "当前未披露研发模态"}
          </p>
        </section>

        <section className="company-profile-section">
          <header>
            <div>
              <span>TARGET LANDSCAPE</span>
              <h3>关键关联靶点</h3>
            </div>
            <Dna size={18} />
          </header>
          {targets.length ? (
            <ol className="company-asset-list">
              {targets.slice(0, 10).map(([id, name]) => (
                <li key={id}>
                  <button type="button" onClick={() => onOpenTypedEntity("target", id)}>
                    {name}
                  </button>
                  <span>关联靶点</span>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title="暂无关联靶点" />
          )}
        </section>
      </div>

      <section className="company-profile-section">
        <header>
          <div>
            <span>DISEASE BURDEN</span>
            <h3>最新疾病负担观测</h3>
          </div>
          <button type="button" onClick={() => onOpenEpidemiology(data.entity.id)} disabled={!data.epidemiology.total}>
            进入流行病学数据库
          </button>
        </header>
        <EpidemiologyTable items={data.epidemiology.items.slice(0, 5)} onOpen={() => undefined} compact />
      </section>

      <DossierCoverageDisclosure
        available={data.coverage.filter((item) => item.total > 0).length}
        total={data.coverage.length}
      >
        <section className="company-profile-section company-profile-coverage">
          <header>
            <div>
              <span>COVERAGE</span>
              <h3>领域数据覆盖</h3>
            </div>
            <time dateTime={data.as_of} title="本次档案查询时间，不代表所有来源的最后更新时间">
              查询时间 {formatDate(data.as_of, true)}
            </time>
          </header>
          <ScrollableTableRegion ariaLabel="疾病档案领域数据覆盖">
            <table aria-label="疾病档案领域数据覆盖">
              <thead>
                <tr>
                  <th>领域</th>
                  <th>总量</th>
                  <th>本次返回</th>
                  <th>状态</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>流行病学</td>
                  <td>{data.epidemiology.total}</td>
                  <td>{data.epidemiology.items.length}</td>
                  <td>
                    <StatusBadge value={data.epidemiology.total ? "available" : "empty"} />
                  </td>
                  <td>疾病、人群、地区和统计口径下的观测数据</td>
                </tr>
                {data.coverage.map((item) => (
                  <tr key={item.domain}>
                    <td>{coverageLabel(item.domain)}</td>
                    <td>{item.total}</td>
                    <td>{item.returned}</td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                    <td>{item.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          {data.warnings?.map((warning) => (
            <p className="inline-alert" key={warning}>
              <ShieldCheck size={15} /> {warning}
            </p>
          ))}
        </section>
      </DossierCoverageDisclosure>
    </div>
  );
}

function EpidemiologyPanel({
  data,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenAll,
}: {
  data: DiseaseDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DossierEntityOpener;
  onOpenAll: () => void;
}) {
  return (
    <section className="company-profile-section disease-epidemiology-panel">
      <header>
        <div>
          <span>EPIDEMIOLOGY AND BURDEN</span>
          <h3>流行病学与疾病负担</h3>
        </div>
        <button type="button" onClick={onOpenAll}>
          进入完整数据库
        </button>
      </header>
      <dl className="dossier-metrics">
        <div>
          <dt>观测记录</dt>
          <dd>{data.epidemiology.total}</dd>
        </div>
        <div>
          <dt>标准患者人群</dt>
          <dd>{data.summary.patient_population_count}</dd>
        </div>
        <div>
          <dt>统计指标</dt>
          <dd>{data.summary.measures?.length ?? 0}</dd>
        </div>
        <div>
          <dt>覆盖地区</dt>
          <dd>{data.summary.geographies?.length ?? 0}</dd>
        </div>
      </dl>
      <EpidemiologyTable
        items={data.epidemiology.items}
        onOpen={onOpen}
        onOpenEntity={onOpenEntity}
        onOpenTypedEntity={onOpenTypedEntity}
      />
      {data.epidemiology.warnings?.map((warning) => (
        <p className="inline-alert" key={warning}>
          <ShieldCheck size={15} /> {warning}
        </p>
      ))}
    </section>
  );
}

function EpidemiologyTable({
  items,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  compact = false,
}: {
  items: EpidemiologyObservationSearchItemRead[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity?: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  compact?: boolean;
}) {
  if (!items.length) return <EmptyState title="暂无疾病负担观测" detail="当前可用来源和更新时间范围内没有可展示记录" />;
  return (
    <ScrollableTableRegion ariaLabel={compact ? "最新疾病负担观测" : "疾病流行病学观测"}>
      <table aria-label={compact ? "最新疾病负担观测" : "疾病流行病学观测"}>
        <thead>
          <tr>
            <th>指标 / 估计值</th>
            <th>地区 / 人群</th>
            <th>观察期</th>
            <th>发布机构</th>
            <th>方法学</th>
            {compact ? null : <th aria-label="原始证据" />}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{measureLabels[item.measure] ?? item.measure}</strong>
                <small className="table-secondary">
                  {formatNumber(item.value)} {item.unit}
                </small>
              </td>
              <td>
                {item.geography}
                <small className="table-secondary">{item.patient_population?.name ?? item.population_scope}</small>
              </td>
              <td>{periodLabel(item)}</td>
              <td>
                {item.publisher_entity && onOpenEntity ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => {
                      const entityId = item.publisher_entity?.id ?? "";
                      if (onOpenTypedEntity && item.publisher_entity) {
                        onOpenTypedEntity(item.publisher_entity.entity_type, entityId);
                      } else {
                        onOpenEntity?.(entityId);
                      }
                    }}
                  >
                    {item.publisher_entity.name}
                  </button>
                ) : (
                  (item.publisher_entity?.name ?? "--")
                )}
              </td>
              <td>{item.methodology ?? "未标注"}</td>
              {compact ? null : (
                <td>
                  <ProvenanceButton
                    selection={{
                      resourceType: "epidemiology_observation",
                      resourceId: item.id,
                      label: `${item.disease_entity.name} ${measureLabels[item.measure] ?? item.measure}`,
                    }}
                    onOpen={onOpen}
                  />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

function DiseaseEvidence({
  data,
  onOpen,
  onOpenTypedEntity,
}: {
  data: DiseaseDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTypedEntity: DossierEntityOpener;
}) {
  if (!data.target_evidence.length)
    return <EmptyState title="暂无疾病关联靶点证据" detail="当前可用来源和更新时间范围内没有可展示记录" />;
  return (
    <ScrollableTableRegion ariaLabel="疾病关联靶点证据">
      <table aria-label="疾病关联靶点证据">
        <thead>
          <tr>
            <th>靶点</th>
            <th>类型 / 方向</th>
            <th>研究与人群</th>
            <th>效应</th>
            <th>证据摘要</th>
            <th>观察时间</th>
            <th aria-label="原始证据" />
          </tr>
        </thead>
        <tbody>
          {data.target_evidence.map((item) => (
            <tr key={item.id}>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenTypedEntity("target", item.target_entity_id)}
                >
                  {item.target_name}
                </button>
              </td>
              <td>
                <strong>{evidenceTypeLabel(item.evidence_type)}</strong>
                <small className="table-secondary">{evidenceDirectionLabel(item.direction)}</small>
              </td>
              <td>
                {item.study_name ?? "--"}
                <small className="table-secondary">{item.population ?? "人群未记录"}</small>
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
  );
}

function phaseLabel(value: string | null | undefined) {
  return value ? (phaseLabels[value] ?? value) : "未披露";
}
function formatNumber(value: number | null) {
  return value === null ? "--" : new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 3 }).format(value);
}
function periodLabel(item: EpidemiologyObservationSearchItemRead) {
  return item.period_start === item.period_end
    ? formatDate(item.period_end)
    : `${formatDate(item.period_start)} - ${formatDate(item.period_end)}`;
}
function evidenceTypeLabel(value: string) {
  return (
    (
      {
        genetic_association: "遗传关联",
        expression: "表达",
        functional: "功能验证",
        translational: "转化研究",
        biomarker: "生物标志物",
        safety: "安全性",
      } as Record<string, string>
    )[value] ?? value
  );
}
function evidenceDirectionLabel(value: string) {
  return (
    (
      { supports: "支持疾病机制", opposes: "反对疾病机制", neutral: "中性", unknown: "方向未知" } as Record<
        string,
        string
      >
    )[value] ?? value
  );
}
function coverageLabel(value: string) {
  return (
    (
      {
        relationships: "实体关系",
        evidence: "来源证据",
        activities: "活性数据",
        programs: "研发管线",
        clinical_trials: "临床试验",
        patents: "专利",
        deals: "交易",
        regulatory_events: "监管事件",
        news_events: "新闻与会议",
        structures: "结构",
        target_evidence: "靶点证据",
      } as Record<string, string>
    )[value] ?? value
  );
}
