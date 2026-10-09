import { ShieldCheck } from "lucide-react";
import type { DiseaseDossier } from "../../lib/contracts/disease";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { useLocale } from "../../lib/i18n";
import { diseaseDossierText as t } from "../../lib/i18n/diseaseDossier";
import type { DossierEntityOpener } from "../EntityDossierView";
import { EpidemiologyTable } from "./EpidemiologyTable";

export function EpidemiologyPanel({
  data,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenAll,
}: {
  data: DiseaseDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DossierEntityOpener;
  onOpenAll: () => void;
}) {
  useLocale();
  return (
    <section className="company-profile-section disease-epidemiology-panel">
      <header>
        <div>
          <h3>{t("流行病学与疾病负担")}</h3>
        </div>
        <button type="button" onClick={onOpenAll}>
          {t("进入完整数据库")}
        </button>
      </header>
      <dl className="disease-burden-summary">
        <div>
          <dt>{t("观测记录")}</dt>
          <dd>{data.epidemiology.total}</dd>
        </div>
        <div>
          <dt>{t("标准患者人群")}</dt>
          <dd>{data.summary.patient_population_count}</dd>
        </div>
        <div>
          <dt>{t("统计指标")}</dt>
          <dd>{data.summary.measures?.length ?? 0}</dd>
        </div>
        <div>
          <dt>{t("覆盖地区")}</dt>
          <dd>{data.summary.geographies?.length ?? 0}</dd>
        </div>
      </dl>
      <EpidemiologyTable
        items={data.epidemiology.items}
        onOpen={onOpen}
        onOpenEntity={onOpenEntity}
        onOpenTypedEntity={onOpenTypedEntity}
      />
      {data.epidemiology.warnings?.map((warning) => (
        <p className="inline-alert" key={warning}>
          <ShieldCheck size={15} /> {warning}
        </p>
      ))}
    </section>
  );
}
