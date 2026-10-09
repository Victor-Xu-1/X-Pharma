import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import { dealLabel, rightTypeLabels } from "../../lib/dealDisplay";
import type { DealSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import type { DossierEntityOpener } from "../EntityDossierView";

export function DealRights({ data, onOpenEntity }: { data: DealSearchItemRead; onOpenEntity: DossierEntityOpener }) {
  useLocale();
  return (
    <section>
      <h3>{t("地域权益")}</h3>
      {data.rights.length ? (
        <ScrollableTableRegion ariaLabel={t("交易权益明细")} className="deal-rights-table-frame">
          <table className="deal-rights-table" aria-label={t("交易权益")}>
            <colgroup>
              <col className="deal-rights-holder-column" />
              <col className="deal-rights-type-column" />
              <col className="deal-rights-territory-column" />
              <col className="deal-rights-exclusivity-column" />
              <col className="deal-rights-scope-column" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">{t("权益持有人")}</th>
                <th scope="col">{t("类型")}</th>
                <th scope="col">{t("地区")}</th>
                <th scope="col">{t("独占性")}</th>
                <th scope="col">{t("范围")}</th>
              </tr>
            </thead>
            <tbody>
              {sourceRecordRows(data.rights).map(({ value: right, key }) => (
                <tr key={key}>
                  <td>
                    <button type="button" onClick={() => onOpenEntity("organization", right.holder_entity_id)}>
                      {right.holder_name}
                    </button>
                  </td>
                  <td>{dealLabel(right.right_type, rightTypeLabels)}</td>
                  <td>{right.territory}</td>
                  <td>{right.exclusive == null ? t("未披露") : right.exclusive ? t("独占") : t("非独占")}</td>
                  <td>{right.scope_description ?? t("范围说明未披露")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      ) : (
        <span>{t("地域权益未披露")}</span>
      )}
    </section>
  );
}
