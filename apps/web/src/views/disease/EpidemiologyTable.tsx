import { EmptyState } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { epidemiologyMeasureLabels, epidemiologySexLabels } from "../../lib/epidemiologyDisplay";
import type { EpidemiologyObservationSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { diseaseDossierText as t } from "../../lib/i18n/diseaseDossier";
import { controlledDossierLabel } from "../../lib/i18n/dossierVocabulary";
import type { DossierEntityOpener } from "../EntityDossierView";
import { formatNumber, periodLabel } from "./presentation";

export function EpidemiologyTable({
  items,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  compact = false,
}: {
  items: EpidemiologyObservationSearchItemRead[];
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity?: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  compact?: boolean;
}) {
  useLocale();
  if (!items.length)
    return <EmptyState title={t("暂无疾病负担观测")} detail={t("当前可用来源和更新时间范围内没有可展示记录")} />;
  return (
    <ScrollableTableRegion ariaLabel={compact ? t("最新疾病负担观测") : t("疾病流行病学观测")}>
      <table aria-label={compact ? t("最新疾病负担观测") : t("疾病流行病学观测")}>
        <thead>
          <tr>
            <th>{t("指标 / 估计值")}</th>
            <th>{t("地区 / 人群")}</th>
            <th>{t("观察期")}</th>
            <th>{t("发布机构")}</th>
            <th>{t("方法学")}</th>
            {compact ? null : <th aria-label={t("原始证据")} />}
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>
                <strong>{controlledDossierLabel(item.measure, epidemiologyMeasureLabels)}</strong>
                <small className="table-secondary">
                  {formatNumber(item.value)} {item.unit}
                </small>
                {item.lower_bound != null || item.upper_bound != null ? (
                  <small className="table-secondary">
                    {t("报告界限：{lower} – {upper}", {
                      lower: formatNumber(item.lower_bound),
                      upper: formatNumber(item.upper_bound),
                    })}
                  </small>
                ) : null}
              </td>
              <td>
                {item.geography}
                <small className="table-secondary">{item.patient_population?.name ?? item.population_scope}</small>
                {item.age_group ? (
                  <small className="table-secondary">{t("年龄：{age}", { age: item.age_group })}</small>
                ) : null}
                {item.sex ? (
                  <small className="table-secondary">{controlledDossierLabel(item.sex, epidemiologySexLabels)}</small>
                ) : null}
              </td>
              <td>{periodLabel(item)}</td>
              <td>
                {item.publisher_entity && onOpenEntity ? (
                  <button
                    className="table-link-button"
                    type="button"
                    onClick={() => {
                      const entityId = item.publisher_entity?.id ?? "";
                      if (onOpenTypedEntity && item.publisher_entity) {
                        onOpenTypedEntity(item.publisher_entity.entity_type, entityId);
                      } else {
                        onOpenEntity?.(entityId);
                      }
                    }}
                  >
                    {item.publisher_entity.name}
                  </button>
                ) : (
                  (item.publisher_entity?.name ?? "--")
                )}
              </td>
              <td>
                <span className="disease-methodology">{item.methodology ?? t("未标注")}</span>
                {item.sample_size != null ? (
                  <small className="table-secondary">
                    {t("样本量：{count}", { count: formatNumber(item.sample_size) })}
                  </small>
                ) : null}
              </td>
              {compact ? null : (
                <td>
                  <ProvenanceButton
                    selection={{
                      resourceType: "epidemiology_observation",
                      resourceId: item.id,
                      label: `${item.disease_entity.name} ${controlledDossierLabel(item.measure, epidemiologyMeasureLabels)}`,
                    }}
                    onOpen={onOpen}
                  />
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
