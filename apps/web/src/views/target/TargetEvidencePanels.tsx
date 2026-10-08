import { useState } from "react";
import { EmptyState, formatDate } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { TargetEvidence, TargetRelationship } from "../../lib/contracts/target";
import { entityLabels, relationshipLabel } from "../../lib/entityPresentation";
import { useLocale } from "../../lib/i18n";
import type { TargetEntityOpener } from "./types";

export function Relationships({
  items,
  onOpenEntity,
}: {
  items: TargetRelationship[];
  onOpenEntity: TargetEntityOpener;
}) {
  useLocale();
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
              <td title={item.predicate}>{relationshipLabel(item.predicate)}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() => onOpenEntity(item.related_entity.entity_type, item.related_entity.id)}
                >
                  {item.related_entity.name}
                </button>
              </td>
              <td>{entityLabels()[item.related_entity.entity_type] ?? item.related_entity.entity_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}

export function TargetEvidenceTable({
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
