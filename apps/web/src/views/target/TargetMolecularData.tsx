import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";
import { EmptyState, ErrorState, Spinner, StatusBadge } from "../../components/common";
import { MoleculeDepiction } from "../../components/MoleculeDepiction";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import {
  type Bioactivity,
  type CompoundStructure,
  loadTargetSar,
  type SarActivity,
  type SarFilters,
  targetKeys,
} from "../../lib/contracts/target";

export function TargetSarPanel({
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

export function Activities({
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
export function Structures({
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
