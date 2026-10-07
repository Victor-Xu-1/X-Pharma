import { useQueries, useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import type { CollectionEntity } from "../lib/contracts/collections";
import {
  type DrugComparison,
  type EntityDossier,
  entityDossierKeys,
  loadDrugComparison,
  loadEntityDossier,
} from "../lib/contracts/entityDossier";
import { phaseLabels } from "../lib/dealDisplay";
import { entityTypeLabel } from "../lib/entityPresentation";
import { programModalityLabel } from "../lib/programDisplay";
import { isPublicEntityIdentifierNamespace } from "../lib/publicEntity";
import { EmptyState, ErrorState, formatDate, Spinner } from "./common";
import { EntityIdentityLabel } from "./EntityIdentityLabel";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

type CoverageDomain = EntityDossier["coverage"][number]["domain"];

const coverageRows: ReadonlyArray<{ domain: CoverageDomain; label: string }> = [
  { domain: "relationships", label: "关联信息" },
  { domain: "evidence", label: "资料来源" },
  { domain: "activities", label: "生物活性" },
  { domain: "programs", label: "研发项目" },
  { domain: "clinical_trials", label: "临床试验" },
  { domain: "patents", label: "专利族" },
  { domain: "deals", label: "交易" },
  { domain: "regulatory_events", label: "监管事件" },
  { domain: "news_events", label: "资讯事件" },
  { domain: "structures", label: "化学结构" },
  { domain: "target_evidence", label: "靶点证据" },
];

const programStatusLabels: Record<string, string> = {
  active: "在研",
  inactive: "已停止",
  unknown: "暂未披露",
};

const identifierLabels: Record<string, string> = {
  chembl: "ChEMBL",
  hgnc: "HGNC",
  uniprot: "UniProt",
  nct: "NCT 编号",
  patent_number: "专利号",
  lei: "LEI",
};

function externalIdentifiers(entity: CollectionEntity): string {
  const identifiers = Object.entries(entity.external_ids)
    .filter(([namespace]) => isPublicEntityIdentifierNamespace(namespace))
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([namespace, value]) => `${identifierLabels[namespace] ?? namespace.toLocaleUpperCase()} · ${value}`);
  return identifiers.join(" · ") || "未披露";
}

function coverageValue(dossier: EntityDossier, domain: CoverageDomain): ReactNode {
  const coverage = dossier.coverage.find((item) => item.domain === domain);
  if (!coverage) return <span className="comparison-missing">未提供</span>;
  if (coverage.status === "not_observed") {
    return (
      <span className="comparison-missing" title={coverage.note}>
        未观察到
      </span>
    );
  }
  return (
    <span title={coverage.note}>
      <strong>{coverage.total.toLocaleString()}</strong>
      {coverage.status === "truncated" ? <small>当前返回 {coverage.returned.toLocaleString()}</small> : null}
    </span>
  );
}

function missingValue(): ReactNode {
  return <span className="comparison-missing">未披露</span>;
}

type DrugComparisonProfile = DrugComparison["items"][number];

function summarizedValues(values: string[]): ReactNode {
  const unique = [...new Set(values.map((value) => value.trim()).filter(Boolean))].sort((left, right) =>
    left.localeCompare(right, "zh-CN"),
  );
  if (!unique.length) return missingValue();
  const visible = unique.slice(0, 4);
  return (
    <span title={unique.join("、")}>
      {visible.join("、")}
      {unique.length > visible.length ? ` 等 ${unique.length} 项` : ""}
    </span>
  );
}

function profileStatusSummary(profile: DrugComparisonProfile): ReactNode {
  const entries = Object.entries(profile.program_status_counts);
  if (!entries.length) return missingValue();
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([status, count]) => `${programStatusLabels[status] ?? status}（${count.toLocaleString()}）`)
    .join(" · ");
}

function profilePhase(value: string | null | undefined): ReactNode {
  return value ? (phaseLabels[value] ?? value) : missingValue();
}

function DrugProfileRow({
  label,
  profiles,
  render,
}: {
  label: string;
  profiles: DrugComparisonProfile[];
  render: (profile: DrugComparisonProfile) => ReactNode;
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      {profiles.map((profile) => (
        <td key={profile.entity.id}>{render(profile)}</td>
      ))}
    </tr>
  );
}

function DrugComparisonMatrix({
  profiles,
  onOpenEntity,
}: {
  profiles: DrugComparisonProfile[];
  onOpenEntity: (entity: CollectionEntity) => void;
}) {
  return (
    <ScrollableTableRegion ariaLabel="研发情报对比表" className="entity-comparison-region">
      <table
        className="entity-comparison-table"
        aria-label="研发情报对比表"
        style={{ minWidth: `${170 + profiles.length * 240}px` }}
      >
        <thead>
          <tr>
            <th scope="col">比较维度</th>
            {profiles.map((profile) => (
              <th scope="col" key={profile.entity.id}>
                <button
                  type="button"
                  className="comparison-entity-link"
                  aria-label={`打开 ${profile.entity.name} 详情`}
                  onClick={() => onOpenEntity(profile.entity)}
                >
                  <span>
                    <strong>{profile.entity.name}</strong>
                    <small>药物</small>
                  </span>
                  <ExternalLink size={15} aria-hidden="true" />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="comparison-group-row">
            <th colSpan={profiles.length + 1}>基础信息</th>
          </tr>
          <DrugProfileRow label="类型" profiles={profiles} render={() => "药物"} />
          <DrugProfileRow
            label="说明"
            profiles={profiles}
            render={(profile) => profile.entity.description || missingValue()}
          />
          <DrugProfileRow
            label="资料编号"
            profiles={profiles}
            render={(profile) => externalIdentifiers(profile.entity)}
          />
          <DrugProfileRow label="查询时间" profiles={profiles} render={(profile) => formatDate(profile.as_of, true)} />
          <tr className="comparison-group-row">
            <th colSpan={profiles.length + 1}>研发格局</th>
          </tr>
          <DrugProfileRow
            label="作用靶点"
            profiles={profiles}
            render={(profile) => summarizedValues(profile.target_names)}
          />
          <DrugProfileRow
            label="适应症"
            profiles={profiles}
            render={(profile) => summarizedValues(profile.indication_names)}
          />
          <DrugProfileRow
            label="最高阶段"
            profiles={profiles}
            render={(profile) => profilePhase(profile.summary.highest_phase)}
          />
          <DrugProfileRow
            label="全球最高阶段"
            profiles={profiles}
            render={(profile) => profilePhase(profile.summary.highest_global_phase)}
          />
          <DrugProfileRow
            label="中国最高阶段"
            profiles={profiles}
            render={(profile) => profilePhase(profile.summary.highest_china_phase)}
          />
          <DrugProfileRow
            label="研发机构"
            profiles={profiles}
            render={(profile) => summarizedValues(profile.organization_names)}
          />
          <DrugProfileRow
            label="药物类型"
            profiles={profiles}
            render={(profile) => summarizedValues(profile.summary.modalities.map(programModalityLabel))}
          />
          <DrugProfileRow label="项目状态" profiles={profiles} render={profileStatusSummary} />
          <tr className="comparison-group-row">
            <th colSpan={profiles.length + 1}>研发覆盖</th>
          </tr>
          <DrugProfileRow
            label="研发项目"
            profiles={profiles}
            render={(profile) => profile.summary.program_count.toLocaleString()}
          />
          <DrugProfileRow
            label="作用靶点数"
            profiles={profiles}
            render={(profile) => profile.summary.target_count.toLocaleString()}
          />
          <DrugProfileRow
            label="适应症数"
            profiles={profiles}
            render={(profile) => profile.summary.indication_count.toLocaleString()}
          />
          <DrugProfileRow
            label="研发机构数"
            profiles={profiles}
            render={(profile) => profile.summary.organization_count.toLocaleString()}
          />
          <DrugProfileRow
            label="最近进展"
            profiles={profiles}
            render={(profile) =>
              profile.summary.latest_status_date ? formatDate(profile.summary.latest_status_date) : missingValue()
            }
          />
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

function ComparisonRow({
  label,
  dossiers,
  render,
}: {
  label: string;
  dossiers: EntityDossier[];
  render: (dossier: EntityDossier) => ReactNode;
}) {
  return (
    <tr>
      <th scope="row">{label}</th>
      {dossiers.map((dossier) => (
        <td key={dossier.entity.id}>{render(dossier)}</td>
      ))}
    </tr>
  );
}

export function CollectionComparisonMatrix({
  entities,
  onOpenEntity,
}: {
  entities: CollectionEntity[];
  onOpenEntity: (entity: CollectionEntity) => void;
}) {
  const isDrugComparison = entities.length >= 2 && entities.every((entity) => entity.entity_type === "drug");
  const drugComparison = useQuery({
    queryKey: entityDossierKeys.drugComparison(entities.map((entity) => entity.id)),
    queryFn: ({ signal }) =>
      loadDrugComparison(
        entities.map((entity) => entity.id),
        signal,
      ),
    enabled: isDrugComparison,
  });
  const dossierQueries = useQueries({
    queries:
      entities.length >= 2 && !isDrugComparison
        ? entities.map((entity) => ({
            queryKey: entityDossierKeys.detail(entity.id),
            queryFn: ({ signal }: { signal: AbortSignal }) => loadEntityDossier(entity.id, signal),
          }))
        : [],
  });

  if (entities.length < 2) {
    return <EmptyState title="至少选择两个条目" detail="当前没有可比较的内容" />;
  }
  if (isDrugComparison) {
    if (drugComparison.isPending) return <Spinner label="正在加载药物研发比较" />;
    if (drugComparison.error) {
      return (
        <ErrorState
          message={drugComparison.error instanceof Error ? drugComparison.error.message : "药物研发比较加载失败"}
          retry={() => void drugComparison.refetch()}
        />
      );
    }
    const profiles = drugComparison.data?.items ?? [];
    if (profiles.length !== entities.length) {
      return <ErrorState message="药物对比信息加载不完整" retry={() => void drugComparison.refetch()} />;
    }
    return <DrugComparisonMatrix profiles={profiles} onOpenEntity={onOpenEntity} />;
  }
  if (dossierQueries.some((query) => query.isPending)) {
    return <Spinner label="正在生成对比表" />;
  }
  const failed = dossierQueries
    .map((query, index) => ({ entity: entities[index], error: query.error }))
    .filter((item) => item.error);
  if (failed.length) {
    return (
      <ErrorState
        message={failed
          .map(
            ({ entity, error }) =>
              `${entity?.name ?? "条目"}：${error instanceof Error ? error.message : "资料加载失败"}`,
          )
          .join("；")}
        retry={() => dossierQueries.forEach((query) => void query.refetch())}
      />
    );
  }

  const dossiers = dossierQueries
    .map((query) => query.data)
    .filter((dossier): dossier is EntityDossier => Boolean(dossier));
  if (dossiers.length !== entities.length) {
    return (
      <ErrorState message="对比信息加载不完整" retry={() => dossierQueries.forEach((query) => void query.refetch())} />
    );
  }
  return (
    <ScrollableTableRegion ariaLabel="研发情报对比表" className="entity-comparison-region">
      <table
        className="entity-comparison-table"
        aria-label="研发情报对比表"
        style={{ minWidth: `${170 + dossiers.length * 240}px` }}
      >
        <thead>
          <tr>
            <th scope="col">比较维度</th>
            {dossiers.map((dossier) => (
              <th scope="col" key={dossier.entity.id}>
                <button
                  type="button"
                  className="comparison-entity-link"
                  aria-label={`打开 ${dossier.entity.name} 详情`}
                  onClick={() => onOpenEntity(dossier.entity)}
                >
                  <span>
                    <strong>{dossier.entity.name}</strong>
                    <small>{entityTypeLabel(dossier.entity)}</small>
                  </span>
                  <ExternalLink size={15} aria-hidden="true" />
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr className="comparison-group-row">
            <th colSpan={dossiers.length + 1}>基础信息</th>
          </tr>
          <ComparisonRow
            label="类型"
            dossiers={dossiers}
            render={(dossier) => <EntityIdentityLabel entity={dossier.entity} />}
          />
          <ComparisonRow
            label="说明"
            dossiers={dossiers}
            render={(dossier) => dossier.entity.description || <span className="comparison-missing">未披露</span>}
          />
          <ComparisonRow
            label="资料编号"
            dossiers={dossiers}
            render={(dossier) => externalIdentifiers(dossier.entity)}
          />
          <ComparisonRow label="查询时间" dossiers={dossiers} render={(dossier) => formatDate(dossier.as_of, true)} />
          <tr className="comparison-group-row">
            <th colSpan={dossiers.length + 1}>信息收录</th>
          </tr>
          {coverageRows.map(({ domain, label }) => (
            <ComparisonRow
              key={domain}
              label={label}
              dossiers={dossiers}
              render={(dossier) => coverageValue(dossier, domain)}
            />
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
