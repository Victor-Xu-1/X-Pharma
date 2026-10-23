import { useState } from "react";
import { EmptyState, formatDate } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { TargetEvidence, TargetRelationship } from "../../lib/contracts/target";
import { entityTypeLabel, relationshipLabel } from "../../lib/entityPresentation";
import { formattingLocale, useMessages } from "../../lib/i18n";
import {
  targetEvidenceDirectionKeys,
  targetEvidenceDirectionLabel,
  targetEvidenceMessages,
  targetEvidenceTypeKeys,
  targetEvidenceTypeLabel,
} from "../../lib/i18n/targetEvidence";
import type { TargetEntityOpener } from "./types";

export function Relationships({
  items,
  onOpenEntity,
}: {
  items: TargetRelationship[];
  onOpenEntity: TargetEntityOpener;
}) {
  const text = useMessages(targetEvidenceMessages);
  if (!items.length) return <EmptyState title={text("暂无关联实体")} />;
  return (
    <ScrollableTableRegion ariaLabel={text("靶点实体关系")}>
      <table aria-label={text("靶点实体关系")}>
        <thead>
          <tr>
            <th>{text("方向")}</th>
            <th>{text("关系")}</th>
            <th>{text("关联实体")}</th>
            <th>{text("类型")}</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.direction === "outgoing" ? text("指向") : text("来自")}</td>
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
              <td>{entityTypeLabel(item.related_entity)}</td>
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
  const text = useMessages(targetEvidenceMessages);
  const number = new Intl.NumberFormat(formattingLocale());
  const [evidenceType, setEvidenceType] = useState("");
  const [direction, setDirection] = useState("");
  const filtered = items.filter(
    (item) => (!evidenceType || item.evidence_type === evidenceType) && (!direction || item.direction === direction),
  );
  if (!items.length) {
    return (
      <EmptyState
        title={text("暂无遗传、表达或转化证据")}
        detail={text("当前可用来源和更新时间范围内未观察到记录，不代表该靶点不存在相关证据")}
      />
    );
  }
  return (
    <div className="target-evidence-panel">
      <fieldset className="target-evidence-filters">
        <legend className="sr-only">{text("转化证据筛选")}</legend>
        <label>
          {text("证据类型")}
          <select
            aria-label={text("证据类型")}
            value={evidenceType}
            onChange={(event) => setEvidenceType(event.target.value)}
          >
            <option value="">{text("全部")}</option>
            {Object.entries(targetEvidenceTypeKeys).map(([value, key]) => (
              <option value={value} key={value}>
                {text(key)}
              </option>
            ))}
          </select>
        </label>
        <label>
          {text("证据方向")}
          <select
            aria-label={text("证据方向")}
            value={direction}
            onChange={(event) => setDirection(event.target.value)}
          >
            <option value="">{text("全部")}</option>
            {Object.entries(targetEvidenceDirectionKeys).map(([value, keys]) => (
              <option value={value} key={value}>
                {text(keys.option)}
              </option>
            ))}
          </select>
        </label>
        <span>
          {text("{shown} / {total} 条", { shown: number.format(filtered.length), total: number.format(items.length) })}
        </span>
      </fieldset>
      {!filtered.length ? (
        <EmptyState title={text("当前筛选条件下无匹配证据")} />
      ) : (
        <ScrollableTableRegion ariaLabel={text("靶点转化证据")}>
          <table aria-label={text("靶点转化证据")}>
            <thead>
              <tr>
                <th>{text("类型 / 方向")}</th>
                <th>{text("疾病")}</th>
                <th>{text("研究与人群")}</th>
                <th>{text("组织 / 变异")}</th>
                <th>{text("效应")}</th>
                <th>{text("证据摘要")}</th>
                <th>{text("观察时间")}</th>
                <th aria-label={text("原始证据")} />
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
                    <small className="table-secondary">{item.population ?? text("人群未记录")}</small>
                  </td>
                  <td>
                    {item.tissue ?? "--"}
                    <small className="table-secondary">{item.variant ?? text("变异未记录")}</small>
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
