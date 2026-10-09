import { EmptyState, formatDate } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DiseaseDossier } from "../../lib/contracts/disease";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { useLocale } from "../../lib/i18n";
import { diseaseDossierText as t } from "../../lib/i18n/diseaseDossier";
import { targetEvidenceDirectionLabel, targetEvidenceTypeLabel } from "../../lib/i18n/targetEvidence";
import type { DossierEntityOpener } from "../EntityDossierView";

export function DiseaseEvidence({
  data,
  onOpen,
  onOpenTypedEntity,
}: {
  data: DiseaseDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTypedEntity: DossierEntityOpener;
}) {
  useLocale();
  if (!data.target_evidence.length)
    return <EmptyState title={t("暂无疾病关联靶点证据")} detail={t("当前可用来源和更新时间范围内没有可展示记录")} />;
  return (
    <ScrollableTableRegion ariaLabel={t("疾病关联靶点证据")}>
      <table aria-label={t("疾病关联靶点证据")}>
        <thead>
          <tr>
            <th>{t("靶点")}</th>
            <th>{t("类型 / 方向")}</th>
            <th>{t("研究与人群")}</th>
            <th>{t("组织 / 变异")}</th>
            <th>{t("效应")}</th>
            <th>{t("证据摘要")}</th>
            <th>{t("观察时间")}</th>
            <th aria-label={t("原始证据")} />
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
                <strong>{targetEvidenceTypeLabel(item.evidence_type)}</strong>
                <small className="table-secondary">{targetEvidenceDirectionLabel(item.direction, "disease")}</small>
              </td>
              <td>
                {item.study_name ?? "--"}
                <small className="table-secondary">{item.population ?? t("人群未记录")}</small>
              </td>
              <td>
                {item.tissue ?? t("组织未记录")}
                <small className="table-secondary">{item.variant ?? t("变异未记录")}</small>
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
