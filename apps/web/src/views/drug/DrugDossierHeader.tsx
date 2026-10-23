import { ChevronDown, Pill } from "lucide-react";
import { formatDate } from "../../components/common";
import { EntityNames } from "../../components/EntityNames";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../../lib/i18n/programVocabulary";
import "./DrugDossierHeader.css";

/** Presentation only; dossier queries, navigation and scientific facts retain their existing owners. */
export function DrugDossierHeader({ data }: { data: DrugDossier }) {
  const primary = [
    { key: "phase", label: t("最高阶段"), value: phaseLabel(data.summary.highest_phase) },
    { key: "programs", label: t("研发项目"), value: data.summary.program_count },
    {
      key: "associations",
      label: t("靶点 / 适应症"),
      value: `${data.summary.target_count} / ${data.summary.indication_count}`,
    },
  ];

  return (
    <section className="drug-header-section" aria-label={t("药物档案摘要")}>
      <header className="drug-profile-header">
        <div className="drug-profile-symbol">
          <Pill size={23} aria-hidden="true" />
        </div>
        <div className="drug-profile-identity">
          <h2>{data.entity.name}</h2>
          <p>{data.entity.description ?? t("暂无药物摘要")}</p>
        </div>
      </header>
      <dl className="drug-profile-metrics drug-header-primary-metrics">
        {primary.map(({ key, label, value }) => (
          <div key={key}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <details className="drug-header-details">
        <summary>
          {t("地区阶段与药物标识")}
          <ChevronDown size={14} aria-hidden="true" />
        </summary>
        <div className="drug-header-detail-content">
          <dl className="drug-header-secondary-metrics">
            <div>
              <dt>{t("全球 / 中国")}</dt>
              <dd>
                {phaseLabel(data.summary.highest_global_phase)} / {phaseLabel(data.summary.highest_china_phase)}
              </dd>
            </div>
            <div>
              <dt>{t("研发机构")}</dt>
              <dd>{data.summary.organization_count}</dd>
            </div>
            <div>
              <dt>{t("最新状态")}</dt>
              <dd>
                {data.summary.latest_status_date ? (
                  <time dateTime={data.summary.latest_status_date}>{formatDate(data.summary.latest_status_date)}</time>
                ) : (
                  "--"
                )}
              </dd>
            </div>
          </dl>
          <EntityNames entity={data.entity} />
        </div>
      </details>
    </section>
  );
}
