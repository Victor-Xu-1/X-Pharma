import { ShieldCheck } from "lucide-react";
import type { EntityDossier } from "../../lib/contracts/entityDossier";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { publicEntityAttributeLabel, publicEntityAttributes } from "../../lib/publicEntity";
import type { EntityDossierSection } from "../../lib/workspaceRouting";
import { formatAttribute } from "./presentation";
import { coverageSectionMap, dossierDomainLabel } from "./vocabulary";

export function DossierOverview({
  data,
  onOpenSection,
}: {
  data: EntityDossier;
  onOpenSection: (section: EntityDossierSection) => void;
}) {
  useLocale();
  return (
    <div className="entity-dossier-overview">
      <section className="entity-summary-section">
        <h3>{t("公开标识与属性")}</h3>
        <dl className="entity-attribute-grid">
          {Object.entries(data.entity.external_ids).map(([key, value]) => (
            <div key={key}>
              <dt>{key}</dt>
              <dd>{value}</dd>
            </div>
          ))}
          {publicEntityAttributes(data.entity).map(([key, value]) => (
            <div key={key}>
              <dt>{publicEntityAttributeLabel(key)}</dt>
              <dd>{formatAttribute(value)}</dd>
            </div>
          ))}
          {!Object.keys(data.entity.external_ids).length && !publicEntityAttributes(data.entity).length ? (
            <div>
              <dd>{t("暂无扩展标识或属性")}</dd>
            </div>
          ) : null}
        </dl>
      </section>
      <section className="coverage-section">
        <h3>{t("数据覆盖与缺口")}</h3>
        <div className="coverage-grid">
          {data.coverage.map((item) => (
            <article key={item.domain} className={item.status}>
              <span>{dossierDomainLabel(item.domain)}</span>
              <strong>{item.total}</strong>
              <small>{item.note}</small>
              {coverageSectionMap[item.domain] ? (
                <button
                  className="coverage-open-button"
                  type="button"
                  disabled={item.total === 0}
                  onClick={() => onOpenSection(coverageSectionMap[item.domain] ?? "overview")}
                >
                  {t("查看{domain}", { domain: dossierDomainLabel(item.domain) })}
                </button>
              ) : null}
            </article>
          ))}
        </div>
      </section>
      {data.warnings?.map((warning) => (
        <p className="inline-alert" key={warning}>
          <ShieldCheck size={15} /> {warning}
        </p>
      ))}
    </div>
  );
}
