import { useQueries, useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";
import type { CollectionEntity } from "../lib/contracts/collections";
import {
  type EntityDossier,
  entityDossierKeys,
  loadDrugComparison,
  loadEntityDossier,
} from "../lib/contracts/entityDossier";
import { entityTypeLabel } from "../lib/entityPresentation";
import { useMessages } from "../lib/i18n";
import { collectionMatrixMessages } from "../lib/i18n/collectionMatrix";
import { coverageRows, coverageValue, externalIdentifiers } from "./collectionComparisonPresentation";
import { EmptyState, ErrorState, formatDate, Spinner } from "./common";
import { DrugComparisonMatrix } from "./DrugComparisonMatrix";
import { EntityIdentityLabel } from "./EntityIdentityLabel";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

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
  const text = useMessages(collectionMatrixMessages);
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
    return <EmptyState title={text("至少选择两个条目")} detail={text("当前没有可比较的内容")} />;
  }
  if (isDrugComparison) {
    if (drugComparison.isPending) return <Spinner label={text("正在加载药物研发比较")} />;
    if (drugComparison.error) {
      return (
        <ErrorState
          message={drugComparison.error instanceof Error ? drugComparison.error.message : text("药物研发比较加载失败")}
          retry={() => void drugComparison.refetch()}
        />
      );
    }
    const profiles = drugComparison.data?.items ?? [];
    if (profiles.length !== entities.length) {
      return <ErrorState message={text("药物对比信息加载不完整")} retry={() => void drugComparison.refetch()} />;
    }
    return <DrugComparisonMatrix profiles={profiles} onOpenEntity={onOpenEntity} />;
  }
  if (dossierQueries.some((query) => query.isPending)) {
    return <Spinner label={text("正在生成对比表")} />;
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
              `${entity?.name ?? text("条目")}：${error instanceof Error ? error.message : text("资料加载失败")}`,
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
      <ErrorState
        message={text("对比信息加载不完整")}
        retry={() => dossierQueries.forEach((query) => void query.refetch())}
      />
    );
  }
  return (
    <ScrollableTableRegion ariaLabel={text("研发情报对比表")} className="entity-comparison-region">
      <table
        className="entity-comparison-table"
        aria-label={text("研发情报对比表")}
        style={{ minWidth: `${170 + dossiers.length * 240}px` }}
      >
        <thead>
          <tr>
            <th scope="col">{text("比较维度")}</th>
            {dossiers.map((dossier) => (
              <th scope="col" key={dossier.entity.id}>
                <button
                  type="button"
                  className="comparison-entity-link"
                  aria-label={text("打开 {name} 详情", { name: dossier.entity.name })}
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
            <th colSpan={dossiers.length + 1}>{text("基础信息")}</th>
          </tr>
          <ComparisonRow
            label={text("类型")}
            dossiers={dossiers}
            render={(dossier) => <EntityIdentityLabel entity={dossier.entity} />}
          />
          <ComparisonRow
            label={text("说明")}
            dossiers={dossiers}
            render={(dossier) =>
              dossier.entity.description || <span className="comparison-missing">{text("未披露")}</span>
            }
          />
          <ComparisonRow
            label={text("资料编号")}
            dossiers={dossiers}
            render={(dossier) => externalIdentifiers(dossier.entity)}
          />
          <ComparisonRow
            label={text("查询时间")}
            dossiers={dossiers}
            render={(dossier) => formatDate(dossier.as_of, true)}
          />
          <tr className="comparison-group-row">
            <th colSpan={dossiers.length + 1}>{text("信息收录")}</th>
          </tr>
          {coverageRows.map(({ domain, label }) => (
            <ComparisonRow
              key={domain}
              label={text(label)}
              dossiers={dossiers}
              render={(dossier) => coverageValue(dossier, domain)}
            />
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
