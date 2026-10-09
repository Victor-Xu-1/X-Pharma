import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { localizedFullDevelopmentPhase } from "../../lib/i18n/programVocabulary";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import { openDossierEntity } from "./navigation";
import type { DossierEntityOpener, DossierSectionProps } from "./types";

export function Programs({
  data,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
}: DossierSectionProps & { onOpenEntity: (entityId: string) => void; onOpenTypedEntity?: DossierEntityOpener }) {
  useLocale();
  if (!data.programs.length) return <EmptyState title={t("暂无关联研发管线")} />;
  return (
    <ScrollableTableRegion ariaLabel={t("关联研发管线")}>
      <table aria-label={t("关联研发管线")}>
        <thead>
          <tr>
            <th>{t("药物")}</th>
            <th>{t("公司")}</th>
            <th>{t("适应症")}</th>
            <th>{t("靶点")}</th>
            <th>{t("机制/模态")}</th>
            <th>{t("阶段")}</th>
            <th>{t("状态日期")}</th>
            <th>{t("阶段历史与里程碑")}</th>
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
                    {t("{phases} 个阶段 · {milestones} 个里程碑", {
                      phases: item.status_history?.length ?? 0,
                      milestones: item.milestones?.length ?? 0,
                    })}
                  </summary>
                  <ol>
                    {sourceRecordRows(item.status_history ?? []).map(({ value: event, key }) => (
                      <li key={key}>
                        <strong>{localizedFullDevelopmentPhase(event.phase)}</strong> · {formatDate(event.effective_at)}
                        {event.geography ? ` · ${event.geography}` : ""}
                      </li>
                    ))}
                    {sourceRecordRows(item.milestones ?? []).map(({ value: event, key }) => (
                      <li key={key}>
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
