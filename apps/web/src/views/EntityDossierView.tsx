import type { DossierEntityOpener, DossierSectionProps } from "./dossier/types";

export type { DossierEntityOpener } from "./dossier/types";

import { openDossierEntity } from "./dossier/navigation";
import { Relationships } from "./dossier/Relationships";

export { Relationships };

import { Patents } from "./dossier/Patents";

export { Patents };

import { Regulatory } from "./dossier/Regulatory";

export { Regulatory };

import { News } from "./dossier/News";

export { News };

import { Structures } from "./dossier/Structures";

export { Structures };

import { useQuery } from "@tanstack/react-query";
import { CalendarDays, Landmark, Network, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";

import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../components/common";
import { DossierActivityTable as Activities } from "../components/DossierActivityTable";
import { EntityNames } from "../components/EntityNames";
import { ProvenanceButton, RecordProvenanceDrawer } from "../components/RecordProvenanceDrawer";
import { ResearchTabList, type ResearchTabOption } from "../components/ResearchTabList";
import { ScrollableTableRegion } from "../components/ScrollableTableRegion";
import { companyKeys, loadCompanyTimeline } from "../lib/contracts/company";
import { type EntityDossier, entityDossierKeys, loadEntityDossier } from "../lib/contracts/entityDossier";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { directionLabels, partyRoleLabels, phaseLabels } from "../lib/dealDisplay";
import { entityTypeLabel } from "../lib/entityPresentation";
import type { CompanyTimelineResult } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import { publicEntityAttributeLabel, publicEntityAttributes } from "../lib/publicEntity";
import type { Entity } from "../lib/types";
import type { EntityDossierSection } from "../lib/workspaceRouting";

export { Activities };

const domainLabels: Record<string, string> = {
  relationships: "实体关系",
  evidence: "来源证据",
  activities: "活性数据",
  programs: "研发管线",
  clinical_trials: "临床试验",
  patents: "专利",
  deals: "交易",
  regulatory_events: "监管事件",
  news_events: "新闻与会议",
  structures: "化学结构",
};

const tabs: Array<ResearchTabOption<EntityDossierSection>> = [
  { key: "overview", label: "概览" },
  { key: "company_intelligence", label: "公司情报" },
  { key: "relationships", label: "关系网络" },
  { key: "programs", label: "研发管线" },
  { key: "activities", label: "活性数据" },
  { key: "clinical_trials", label: "临床试验" },
  { key: "patents", label: "专利" },
  { key: "deals", label: "交易" },
  { key: "regulatory_events", label: "监管" },
  { key: "news_events", label: "动态" },
  { key: "structures", label: "结构" },
];

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

  if (!entity) return <EmptyState title="尚未选择领域实体" detail="请从基础查询结果中打开一个实体" />;
  if (dossier.error) {
    return (
      <ErrorState
        message={dossier.error instanceof Error ? dossier.error.message : "领域档案加载失败"}
        retry={() => void dossier.refetch()}
      />
    );
  }
  if (!dossier.data) return <Spinner label={`正在加载 ${entity.name} 领域档案`} />;

  const data = dossier.data;
  const visibleTabs =
    data.entity.entity_type === "organization" ? tabs : tabs.filter((tab) => tab.key !== "company_intelligence");
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
            <p>{data.entity.description ?? "暂无实体摘要"}</p>
          </div>
        </header>
        <EntityNames entity={data.entity} />

        <dl className="dossier-metrics entity-dossier-metrics">
          <div>
            <dt>关联记录</dt>
            <dd>{totalRecords}</dd>
          </div>
          <div>
            <dt>有数据领域</dt>
            <dd>
              {availableDomains} / {data.coverage.length}
            </dd>
          </div>
          <div>
            <dt>直接关系</dt>
            <dd>{data.relationships.length}</dd>
          </div>
          <div>
            <dt>查询时间</dt>
            <dd title="本次档案查询时间，不代表所有来源的最后更新时间">{formatDate(data.as_of, true)}</dd>
          </div>
        </dl>

        <ResearchTabList
          tabs={visibleTabs}
          activeTab={effectiveSection}
          onChange={onSectionChange}
          ariaLabel="领域档案视图"
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

const coverageSectionMap: Partial<Record<string, EntityDossierSection>> = {
  relationships: "relationships",
  activities: "activities",
  programs: "programs",
  clinical_trials: "clinical_trials",
  patents: "patents",
  deals: "deals",
  regulatory_events: "regulatory_events",
  news_events: "news_events",
  structures: "structures",
};

function DossierOverview({
  data,
  onOpenSection,
}: {
  data: EntityDossier;
  onOpenSection: (section: EntityDossierSection) => void;
}) {
  return (
    <div className="entity-dossier-overview">
      <section className="entity-summary-section">
        <h3>公开标识与属性</h3>
        <dl className="entity-attribute-grid">
          {Object.entries(data.entity.external_ids).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
          {publicEntityAttributes(data.entity).map(([key, value]) => (
            <div key={key}>
              <dt>{publicEntityAttributeLabel(key)}</dt>
              <dd>{formatAttribute(value)}</dd>
            </div>
          ))}
          {!Object.keys(data.entity.external_ids).length && !publicEntityAttributes(data.entity).length ? (
            <div>
              <dd>暂无扩展标识或属性</dd>
            </div>
          ) : null}
        </dl>
      </section>
      <section className="coverage-section">
        <h3>数据覆盖与缺口</h3>
        <div className="coverage-grid">
          {data.coverage.map((item) => (
            <article key={item.domain} className={item.status}>
              <span>{domainLabels[item.domain] ?? item.domain}</span>
              <strong>{item.total}</strong>
              <small>{item.note}</small>
              {coverageSectionMap[item.domain] ? (
                <button
                  className="coverage-open-button"
                  type="button"
                  disabled={item.total === 0}
                  onClick={() => onOpenSection(coverageSectionMap[item.domain] ?? "overview")}
                >
                  查看{domainLabels[item.domain] ?? item.domain}
                </button>
              ) : null}
            </article>
          ))}
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

function CompanyIntelligence({
  data,
  timeline,
  loading,
  error,
  retry,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  data: EntityDossier;
  timeline: CompanyTimelineResult | undefined;
  loading: boolean;
  error: Error | null;
  retry: () => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DossierEntityOpener;
}) {
  const programCoverage = data.coverage.find((item) => item.domain === "programs");
  const dealCoverage = data.coverage.find((item) => item.domain === "deals");

  return (
    <div className="company-intelligence-view">
      <dl className="dossier-metrics company-intelligence-metrics">
        <div>
          <dt>研发管线</dt>
          <dd>{programCoverage?.total ?? data.programs.length}</dd>
        </div>
        <div>
          <dt>关联交易</dt>
          <dd>{dealCoverage?.total ?? data.deals.length}</dd>
        </div>
        <div>
          <dt>有日期事件</dt>
          <dd>{timeline?.total ?? "--"}</dd>
        </div>
        <div>
          <dt>时间线截至</dt>
          <dd>{formatDate(timeline?.as_of ?? data.as_of)}</dd>
        </div>
      </dl>

      <section className="company-intelligence-section">
        <header>
          <div>
            <span>PIPELINE</span>
            <h3>公司研发管线</h3>
          </div>
          <small>{programCoverage?.note}</small>
        </header>
        <Programs data={data} onOpen={onOpen} onOpenEntity={onOpenEntity} onOpenTypedEntity={onOpenTypedEntity} />
      </section>

      <CompanyTimelinePanel
        timeline={timeline}
        loading={loading}
        error={error}
        retry={retry}
        note={dealCoverage?.note}
        onOpen={onOpen}
        onOpenEntity={onOpenEntity}
        onOpenTypedEntity={onOpenTypedEntity}
      />
    </div>
  );
}

export function CompanyTimelinePanel({
  timeline,
  loading,
  error,
  retry,
  note,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  timeline: CompanyTimelineResult | undefined;
  loading: boolean;
  error: Error | null;
  retry: () => void;
  note?: string;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
}) {
  return (
    <section className="company-intelligence-section">
      <header>
        <div>
          <span>ACTIVITY TIMELINE</span>
          <h3>管线状态与交易公告</h3>
        </div>
        <small>{note}</small>
      </header>
      {loading && !timeline ? (
        <Spinner label="正在加载公司时间线" />
      ) : error ? (
        <ErrorState message={error.message || "公司时间线加载失败"} retry={retry} />
      ) : timeline?.items.length ? (
        <ol className="company-event-timeline">
          {timeline.items.map((event) => (
            <li key={event.id}>
              <time>{formatDate(event.occurred_at)}</time>
              <span className={`company-event-marker ${event.event_type}`} aria-hidden="true" />
              <div>
                <span>{event.event_type === "program_status" ? "管线状态" : "交易公告"}</span>
                <h4>{event.title}</h4>
                {event.program ? (
                  <p>
                    <button
                      type="button"
                      onClick={() =>
                        openDossierEntity(onOpenEntity, onOpenTypedEntity, "drug", event.program?.drug_entity_id ?? "")
                      }
                    >
                      {event.program.drug_name}
                    </button>
                    {event.program.target_entity_id && event.program.target_name ? (
                      <>
                        <span> · </span>
                        <button
                          type="button"
                          onClick={() =>
                            openDossierEntity(
                              onOpenEntity,
                              onOpenTypedEntity,
                              "target",
                              event.program?.target_entity_id ?? "",
                            )
                          }
                        >
                          {event.program.target_name}
                        </button>
                      </>
                    ) : null}
                    {event.program.disease_entity_id && event.program.disease_name ? (
                      <>
                        <span> · </span>
                        <button
                          type="button"
                          onClick={() =>
                            openDossierEntity(
                              onOpenEntity,
                              onOpenTypedEntity,
                              "disease",
                              event.program?.disease_entity_id ?? "",
                            )
                          }
                        >
                          {event.program.disease_name}
                        </button>
                      </>
                    ) : null}
                    {event.program.geography ? ` · ${event.program.geography}` : ""}
                  </p>
                ) : null}
                {event.deal ? (
                  <p>
                    {event.deal.party_entities.map((party, index) => (
                      <span key={party.id}>
                        {index > 0 ? " × " : ""}
                        <button
                          type="button"
                          onClick={() =>
                            openDossierEntity(onOpenEntity, onOpenTypedEntity, party.entity_type, party.id)
                          }
                        >
                          {party.name}
                        </button>
                      </span>
                    ))}
                    {event.deal.territory ? ` · ${event.deal.territory}` : ""}
                    {event.deal.total_potential_amount !== null
                      ? ` · 潜在总额 ${formatMoney(event.deal.total_potential_amount, event.deal.currency)}`
                      : ""}
                  </p>
                ) : null}
              </div>
              {event.program ? (
                <ProvenanceButton
                  selection={{
                    resourceType: "development_program",
                    resourceId: event.program.id,
                    label: event.program.drug_name,
                  }}
                  onOpen={onOpen}
                />
              ) : null}
              {event.deal ? (
                <ProvenanceButton
                  selection={{ resourceType: "deal", resourceId: event.deal.id, label: event.deal.name }}
                  onOpen={onOpen}
                />
              ) : null}
            </li>
          ))}
        </ol>
      ) : (
        <EmptyState title="暂无带日期的公司事件" detail="当前管线状态或交易记录缺少可用于排序的明确日期" />
      )}
      {timeline?.warnings?.map((warning) => (
        <p className="inline-alert" key={warning}>
          <ShieldCheck size={15} /> {warning}
        </p>
      ))}
    </section>
  );
}

export function Programs({
  data,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
}: DossierSectionProps & { onOpenEntity: (entityId: string) => void; onOpenTypedEntity?: DossierEntityOpener }) {
  if (!data.programs.length) return <EmptyState title="暂无关联研发管线" />;
  return (
    <ScrollableTableRegion ariaLabel="关联研发管线">
      <table aria-label="关联研发管线">
        <thead>
          <tr>
            <th>药物</th>
            <th>公司</th>
            <th>适应症</th>
            <th>靶点</th>
            <th>机制/模态</th>
            <th>阶段</th>
            <th>状态日期</th>
            <th>阶段历史与里程碑</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data.programs.map((item) => (
            <tr key={item.id}>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => openDossierEntity(onOpenEntity, onOpenTypedEntity, "drug", item.drug_entity_id)}
                >
                  {item.drug_name}
                </button>
              </td>
              <td>
                {item.organization_entity_id && item.organization_name ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() =>
                      openDossierEntity(
                        onOpenEntity,
                        onOpenTypedEntity,
                        "organization",
                        item.organization_entity_id ?? "",
                      )
                    }
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
                    onClick={() =>
                      openDossierEntity(onOpenEntity, onOpenTypedEntity, "disease", item.disease_entity_id ?? "")
                    }
                  >
                    {item.disease_name}
                  </button>
                ) : (
                  "--"
                )}
              </td>
              <td>
                {item.target_entity_id && item.target_name ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() =>
                      openDossierEntity(onOpenEntity, onOpenTypedEntity, "target", item.target_entity_id ?? "")
                    }
                  >
                    {item.target_name}
                  </button>
                ) : (
                  "--"
                )}
              </td>
              <td>{item.mechanism_of_action ?? item.modality ?? "--"}</td>
              <td>
                <StatusBadge value={item.phase} />
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
                        <strong>{event.phase}</strong> · {formatDate(event.effective_at)}
                        {event.geography ? ` · ${event.geography}` : ""}
                      </li>
                    ))}
                    {item.milestones?.map((event) => (
                      <li key={`${event.milestone_type}-${event.occurred_at}-${event.title}`}>
                        <strong>{event.title}</strong> · {formatDate(event.occurred_at)}
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

export function Trials({
  data,
  onOpen,
  onOpenTrial,
}: DossierSectionProps & { onOpenTrial: (trialId: string) => void }) {
  if (!data.clinical_trials.length) return <EmptyState title="暂无关联临床试验" />;
  return (
    <div className="entity-record-list">
      {data.clinical_trials.map((item) => (
        <article key={item.id}>
          <CalendarDays size={18} />
          <div>
            <span>
              {item.registry_id} · {item.phases.join(" / ") || "阶段未记录"}
            </span>
            <h3>
              <button className="table-link-button" type="button" onClick={() => onOpenTrial(item.id)}>
                {item.official_title}
              </button>
            </h3>
            <p>{item.conditions.join("、") || "适应症未记录"}</p>
          </div>
          <StatusBadge value={item.overall_status ?? "unknown"} />
          <ProvenanceButton
            selection={{ resourceType: "clinical_trial", resourceId: item.id, label: item.registry_id }}
            onOpen={onOpen}
          />
        </article>
      ))}
    </div>
  );
}

export function Deals({
  data,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenDeal,
}: DossierSectionProps & {
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  onOpenDeal: (dealId: string) => void;
}) {
  if (!data.deals.length) return <EmptyState title="暂无关联交易" />;
  return (
    <div className="entity-record-list">
      {data.deals.map((item) => (
        <article key={item.id}>
          <Landmark size={18} />
          <div>
            <span>
              {item.deal_type} · {formatDate(item.announced_at)}
            </span>
            <h3>
              <button
                className="table-link-button"
                type="button"
                onClick={() => onOpenDeal(item.id)}
                aria-label={`打开交易详情：${item.name}`}
              >
                {item.name}
              </button>
            </h3>
            <p>
              {directionLabels[item.direction] ?? item.direction} · {item.territory ?? "地域条款未记录"} · 潜在总额{" "}
              {formatMoney(item.total_potential_amount, item.currency)}
            </p>
            <div className="dossier-deal-links">
              <div>
                <span>参与方</span>
                {item.party_roles.length || item.party_entities.length ? (
                  (item.party_roles.length ? item.party_roles : item.party_entities).map((party) => (
                    <button
                      key={`party-${item.id}-${party.id}`}
                      className="inline-link-button"
                      type="button"
                      onClick={() => openDossierEntity(onOpenEntity, onOpenTypedEntity, party.entity_type, party.id)}
                    >
                      {party.name}
                      {"role" in party && typeof party.role === "string"
                        ? ` · ${partyRoleLabels[party.role] ?? party.role}`
                        : ""}
                    </button>
                  ))
                ) : (
                  <small>未披露</small>
                )}
              </div>
              <div>
                <span>资产</span>
                {item.asset_stages.length || item.asset_entities.length ? (
                  (item.asset_stages.length ? item.asset_stages : item.asset_entities).map((asset) => (
                    <button
                      key={`asset-${item.id}-${asset.id}`}
                      className="inline-link-button"
                      type="button"
                      onClick={() => openDossierEntity(onOpenEntity, onOpenTypedEntity, asset.entity_type, asset.id)}
                    >
                      {asset.name}
                      {"current_development_phase" in asset && typeof asset.current_development_phase === "string"
                        ? ` · ${phaseLabels[asset.current_development_phase] ?? asset.current_development_phase}`
                        : ""}
                    </button>
                  ))
                ) : (
                  <small>未披露</small>
                )}
              </div>
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

function formatAttribute(value: unknown): string {
  if (value === null || value === undefined) return "--";
  if (["string", "number", "boolean"].includes(typeof value)) return String(value);
  return JSON.stringify(value);
}

function formatMoney(value: number | null, currency: string | null): string {
  if (value === null) return "--";
  return `${currency ?? ""} ${new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 2 }).format(value)}`.trim();
}
