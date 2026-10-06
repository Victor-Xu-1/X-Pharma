import type { EntityDossier } from "../lib/contracts/entityDossier";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { EmptyState } from "./common";
import { ProvenanceButton } from "./RecordProvenanceDrawer";
import { ScrollableTableRegion } from "./ScrollableTableRegion";

type ActivityDossier = Pick<EntityDossier, "entity" | "relationships" | "activities">;

export function DossierActivityTable({
  data,
  onOpen,
}: {
  data: ActivityDossier;
  onOpen: (selection: ProvenanceSelection) => void;
}) {
  if (!data.activities.length) return <EmptyState title="暂无关联活性数据" />;
  const names = new Map([[data.entity.id, data.entity.name]]);
  for (const relationship of data.relationships) {
    names.set(relationship.related_entity.id, relationship.related_entity.name);
  }
  const hasPchembl = data.activities.some((item) => item.pchembl_value != null);
  function entityName(id: string | null) {
    return id ? <span title={id}>{names.get(id) ?? "名称未加载"}</span> : "未披露";
  }

  return (
    <ScrollableTableRegion ariaLabel="关联活性数据">
      <table aria-label="关联活性数据">
        <thead>
          <tr>
            <th>化合物</th>
            <th>靶点</th>
            <th>类型</th>
            <th>来源报告值</th>
            <th>对齐标准值</th>
            {hasPchembl ? <th>pChEMBL</th> : null}
            <th>来源</th>
            <th aria-label="证据" />
          </tr>
        </thead>
        <tbody>
          {data.activities.map((item) => (
            <tr key={item.id}>
              <td>{entityName(item.compound_entity_id)}</td>
              <td>{entityName(item.target_entity_id)}</td>
              <td>{item.reported_type}</td>
              <td>
                {item.reported_relation} {item.reported_value} {item.reported_units ?? "单位未披露"}
              </td>
              <td>
                {item.standard_value == null ? (
                  "无对齐标准值"
                ) : (
                  <>
                    {item.standard_relation} {item.standard_value} {item.standard_units ?? "单位未披露"}
                  </>
                )}
              </td>
              {hasPchembl ? <td>{item.pchembl_value ?? "未提供"}</td> : null}
              <td>{item.source_system === "chembl" ? "ChEMBL" : item.source_system}</td>
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
