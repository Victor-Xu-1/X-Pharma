import { EmptyState, formatDate } from "../../components/common";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { EntityDossier } from "../../lib/contracts/entityDossier";
import { entityLabels, relationshipLabel } from "../../lib/entityPresentation";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { openDossierEntity } from "./navigation";
import type { DossierEntityOpener } from "./types";

export function Relationships({
  data,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  data: EntityDossier;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
}) {
  useLocale();
  if (!data.relationships.length) return <EmptyState title={t("暂无关联实体关系")} />;
  return (
    <ScrollableTableRegion ariaLabel={t("关联实体关系")}>
      <table aria-label={t("关联实体关系")}>
        <thead>
          <tr>
            <th>{t("方向")}</th>
            <th>{t("关系")}</th>
            <th>{t("关联实体")}</th>
            <th>{t("类型")}</th>
            <th>{t("有效期")}</th>
          </tr>
        </thead>
        <tbody>
          {data.relationships.map((item) => (
            <tr key={item.id}>
              <td>{item.direction === "outgoing" ? t("指向") : t("来自")}</td>
              <td title={item.predicate}>{relationshipLabel(item.predicate)}</td>
              <td>
                <button
                  className="table-link-button"
                  type="button"
                  onClick={() =>
                    openDossierEntity(
                      onOpenEntity,
                      onOpenTypedEntity,
                      item.related_entity.entity_type,
                      item.related_entity.id,
                    )
                  }
                >
                  {item.related_entity.name}
                </button>
              </td>
              <td>{entityLabels()[item.related_entity.entity_type] ?? item.related_entity.entity_type}</td>
              <td>
                {formatDate(item.valid_from)} - {formatDate(item.valid_to)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </ScrollableTableRegion>
  );
}
