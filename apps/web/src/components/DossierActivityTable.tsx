import type { EntityDossier } from "../lib/contracts/entityDossier";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { useLocale } from "../lib/i18n";
import { dossierRecordText as t } from "../lib/i18n/dossierRecords";
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
  useLocale();
  if (!data.activities.length) return <EmptyState title={t("暂无关联活性数据")} />;
  const names = new Map([[data.entity.id, data.entity.name]]);
  for (const relationship of data.relationships) {
    names.set(relationship.related_entity.id, relationship.related_entity.name);
  }
  const hasPchembl = data.activities.some((item) => item.pchembl_value != null);
  function entityName(id: string | null) {
    return id ? <span title={id}>{names.get(id) ?? t("名称未加载")}</span> : t("未披露");
  }

  return (
    <ScrollableTableRegion ariaLabel={t("关联活性数据")}>
      <table aria-label={t("关联活性数据")}>
        <thead>
          <tr>
            <th>{t("化合物")}</th>
            <th>{t("靶点")}</th>
            <th>{t("类型")}</th>
            <th>{t("来源报告值")}</th>
            <th>{t("对齐标准值")}</th>
            {hasPchembl ? <th>pChEMBL</th> : null}
            <th>{t("来源")}</th>
            <th aria-label={t("证据")} />
          </tr>
        </thead>
        <tbody>
          {data.activities.map((item) => (
            <tr key={item.id}>
              <td>{entityName(item.compound_entity_id)}</td>
              <td>{entityName(item.target_entity_id)}</td>
              <td>{item.reported_type}</td>
              <td>
                {item.reported_relation} {item.reported_value} {item.reported_units ?? t("单位未披露")}
              </td>
              <td>
                {item.standard_value == null ? (
                  t("无对齐标准值")
                ) : (
                  <>
                    {item.standard_relation} {item.standard_value} {item.standard_units ?? t("单位未披露")}
                  </>
                )}
              </td>
              {hasPchembl ? <td>{item.pchembl_value ?? t("未提供")}</td> : null}
              <td>{item.source_system === "chembl" ? "ChEMBL" : item.source_system}</td>
              <td>
                <ProvenanceButton
                  selection={{ resourceType: "activity_measurement", resourceId: item.id, label: t("活性记录") }}
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
