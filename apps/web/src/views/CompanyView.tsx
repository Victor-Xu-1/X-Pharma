import { useQuery } from "@tanstack/react-query";
import { Building2, Clock3, FlaskConical, Pill, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { DossierCoverageDisclosure } from "../components/DossierCoverageDisclosure";
import { EntityIdentityNotice } from "../components/EntityIdentityNotice";
import { RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import { type CompanyDossier, companyKeys, loadCompanyDossier } from "../lib/contracts/company";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { isProviderLabel } from "../lib/entityPresentation";
import { phaseLabel } from "../lib/phasePresentation";
import type { Entity } from "../lib/types";
import type { CompanyDossierSection } from "../lib/workspaceRouting";
import { CompanySourceLabelOverview } from "./CompanySourceLabelOverview";
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

const tabs: Array<ResearchTabOption<CompanyDossierSection>> = [
  { key: "overview", label: "公司概览" },
  { key: "pipeline", label: "研发管线" },
  { key: "timeline", label: "公司时间线" },
  { key: "deals", label: "交易合作" },
  { key: "relationships", label: "关联网络" },
  { key: "trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "regulatory", label: "监管" },
  { key: "news", label: "公司动态" },
];

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
  const [provenanceSelection, setProvenanceSelection] = useState<ProvenanceSelection | null>(null);
  const dossier = useQuery({
    queryKey: companyKeys.dossier(company?.id ?? ""),
    queryFn: ({ signal }) => loadCompanyDossier(company?.id ?? "", signal),
    enabled: Boolean(company?.id && company.entity_type === "organization"),
  });

  if (!company) return <EmptyState title="尚未选择公司" detail="请从查询、管线或交易结果中打开公司档案" />;
  if (company.entity_type !== "organization") {
    return <ErrorState message="该深链接不是机构实体，无法打开公司专业档案" />;
  }
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : "公司档案加载失败"}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={`正在加载 ${company.name} 公司档案`} />;

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
            <span>{providerLabel ? "登记申办方名称" : "公司专业档案"}</span>
            <h2>{data.entity.name}</h2>
            {!providerLabel ? <p>{data.entity.description ?? "暂无公司简介"}</p> : null}
          </div>
        </header>

        <EntityIdentityNotice entity={data.entity} />

        {!providerLabel ? (
          <dl className="dossier-metrics company-profile-metrics">
            <div>
              <dt>最高阶段</dt>
              <dd>{phaseLabel(data.summary.highest_phase)}</dd>
            </div>
            <div>
              <dt>研发项目 / 药物</dt>
              <dd>
                {data.summary.program_count} / {data.summary.drug_count}
              </dd>
            </div>
            <div>
              <dt>靶点 / 适应症</dt>
              <dd>
                {data.summary.target_count} / {data.summary.indication_count}
              </dd>
            </div>
            <div>
              <dt>关联交易</dt>
              <dd>{data.summary.deal_count}</dd>
            </div>
            <div>
              <dt>带日期事件</dt>
              <dd>{data.summary.timeline_event_count}</dd>
            </div>
            <div>
              <dt>最近活动</dt>
              <dd>{formatDate(data.summary.latest_activity_at)}</dd>
            </div>
          </dl>
        ) : null}

        <ResearchTabList
          tabs={tabs}
          activeTab={activeSection}
          onChange={onSectionChange}
          ariaLabel="公司专业档案视图"
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

function CompanyOverview({
  data,
  onOpenDrug,
  onOpenSection,
}: {
  data: CompanyDossier;
  onOpenDrug: (drugId: string) => void;
  onOpenSection: (section: CompanyDossierSection) => void;
}) {
  const assets = Array.from(
    new Map(
      data.programs.map((program) => [
        program.drug_entity_id,
        { id: program.drug_entity_id, name: program.drug_name, phase: program.phase, modality: program.modality },
      ]),
    ).values(),
  );
  const phaseDistribution = data.summary.phase_distribution ?? {};
  const maximumPhaseCount = Math.max(1, ...Object.values(phaseDistribution));

  return (
    <div className="company-profile-overview">
      <div className="company-profile-overview-grid">
        <section className="company-profile-section">
          <header>
            <div>
              <span>PIPELINE LANDSCAPE</span>
              <h3>研发阶段分布</h3>
            </div>
            <button type="button" onClick={() => onOpenSection("pipeline")} disabled={!data.programs.length}>
              查看全部管线
            </button>
          </header>
          {Object.keys(phaseDistribution).length ? (
            <ol className="company-phase-distribution" aria-label="公司研发阶段分布">
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
            <FlaskConical size={15} />
            {(data.summary.modalities ?? []).join("、") || "当前未披露研发模态"}
          </p>
        </section>

        <section className="company-profile-section">
          <header>
            <div>
              <span>ASSET PORTFOLIO</span>
              <h3>主要研发资产</h3>
            </div>
            <Pill size={18} />
          </header>
          {assets.length ? (
            <ol className="company-asset-list">
              {assets.slice(0, 8).map((asset) => (
                <li key={asset.id}>
                  <button type="button" onClick={() => onOpenDrug(asset.id)}>
                    {asset.name}
                  </button>
                  <span>{asset.modality ?? "模态未披露"}</span>
                  <StatusBadge value={asset.phase} />
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title="暂无已发布研发资产" />
          )}
        </section>
      </div>

      <section className="company-profile-section">
        <header>
          <div>
            <span>RECENT ACTIVITY</span>
            <h3>最近公司事件</h3>
          </div>
          <button type="button" onClick={() => onOpenSection("timeline")} disabled={!data.timeline.items.length}>
            完整时间线
          </button>
        </header>
        {data.timeline.items.length ? (
          <ol className="company-profile-recent-events">
            {data.timeline.items.slice(0, 5).map((event) => (
              <li key={event.id}>
                <Clock3 size={15} />
                <time>{formatDate(event.occurred_at)}</time>
                <strong>{event.title}</strong>
                <span>{event.event_type === "program_status" ? "管线状态" : "交易公告"}</span>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title="暂无带日期的公司事件" />
        )}
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
          <ScrollableTableRegion ariaLabel="公司档案领域数据覆盖">
            <table aria-label="公司档案领域数据覆盖">
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
          {(data.warnings ?? []).map((warning) => (
            <p className="inline-alert" key={warning}>
              <ShieldCheck size={15} /> {warning}
            </p>
          ))}
        </section>
      </DossierCoverageDisclosure>
    </div>
  );
}

function coverageLabel(value: string): string {
  const labels: Record<string, string> = {
    relationships: "实体关系",
    evidence: "来源证据",
    activities: "活性",
    programs: "研发管线",
    clinical_trials: "临床试验",
    patents: "专利",
    deals: "交易",
    regulatory_events: "监管",
    news_events: "新闻与会议",
    structures: "结构",
    target_evidence: "靶点证据",
  };
  return labels[value] ?? value;
}
