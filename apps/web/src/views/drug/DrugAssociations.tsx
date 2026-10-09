import { Dna } from "lucide-react";
import { EmptyState } from "../../components/common";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { Relationships } from "../EntityDossierView";
import { renderEntityLinks, uniqueProgramEntities } from "./associations";
import type { DrugEntityOpener } from "./types";

export function DrugAssociations({
  data,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  data: DrugDossier;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DrugEntityOpener;
}) {
  const targets = uniqueProgramEntities(data, "target");
  const indications = uniqueProgramEntities(data, "disease");
  const organizations = uniqueProgramEntities(data, "organization");
  const hasProgramAssociations = targets.length + indications.length + organizations.length > 0;
  if (!hasProgramAssociations && !data.relationships.length) {
    return <EmptyState title={t("暂无关联信息")} detail={t("当前数据中未收录该药物的靶点、适应症或研发机构")} />;
  }
  return (
    <div className="drug-relationships-view">
      {hasProgramAssociations ? (
        <section className="drug-profile-section" aria-labelledby="drug-associations-title">
          <header>
            <div>
              <span>{t("研发关联")}</span>
              <h3 id="drug-associations-title">{t("靶点、适应症与研发机构")}</h3>
            </div>
            <Dna size={18} aria-hidden="true" />
          </header>
          <dl className="drug-profile-attribute-strip">
            <div>
              <dt>{t("作用靶点")}</dt>
              <dd>{renderEntityLinks(targets, onOpenTypedEntity)}</dd>
            </div>
            <div>
              <dt>{t("适应症")}</dt>
              <dd>{renderEntityLinks(indications, onOpenTypedEntity)}</dd>
            </div>
            <div>
              <dt>{t("研发机构")}</dt>
              <dd>{renderEntityLinks(organizations, onOpenTypedEntity)}</dd>
            </div>
          </dl>
        </section>
      ) : null}
      {data.relationships.length ? (
        <section className="drug-profile-section" aria-labelledby="drug-other-relationships-title">
          <header>
            <div>
              <span>{t("其他关联")}</span>
              <h3 id="drug-other-relationships-title">{t("其他关联记录")}</h3>
            </div>
          </header>
          <Relationships data={data} onOpenEntity={onOpenEntity} onOpenTypedEntity={onOpenTypedEntity} />
        </section>
      ) : null}
    </div>
  );
}
