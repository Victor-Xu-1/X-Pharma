import { formatDate } from "../../components/common";
import type { EntityDossier } from "../../lib/contracts/entityDossier";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { CompanyTimelineResult } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dossierRecordText as t } from "../../lib/i18n/dossierRecords";
import { CompanyTimelinePanel } from "./CompanyTimelinePanel";
import { Programs } from "./Programs";
import type { DossierEntityOpener } from "./types";

export function CompanyIntelligence({
  data,
  timeline,
  loading,
  error,
  retry,
  onOpen,
  onOpenEntity,
  onOpenTypedEntity,
}: {
  data: EntityDossier;
  timeline: CompanyTimelineResult | undefined;
  loading: boolean;
  error: Error | null;
  retry: () => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity: DossierEntityOpener;
}) {
  useLocale();
  const programCoverage = data.coverage.find((item) => item.domain === "programs");
  const dealCoverage = data.coverage.find((item) => item.domain === "deals");

  return (
    <div className="company-intelligence-view">
      <dl className="dossier-metrics company-intelligence-metrics">
        <div>
          <dt>{t("研发管线")}</dt>
          <dd>{programCoverage?.total ?? data.programs.length}</dd>
        </div>
        <div>
          <dt>{t("关联交易")}</dt>
          <dd>{dealCoverage?.total ?? data.deals.length}</dd>
        </div>
        <div>
          <dt>{t("有日期事件")}</dt>
          <dd>{timeline?.total ?? "--"}</dd>
        </div>
        <div>
          <dt>{t("时间线截至")}</dt>
          <dd>{formatDate(timeline?.as_of ?? data.as_of)}</dd>
        </div>
      </dl>

      <section className="company-intelligence-section">
        <header>
          <div>
            <h3>{t("公司研发管线")}</h3>
          </div>
          <small>{programCoverage?.note}</small>
        </header>
        <Programs data={data} onOpen={onOpen} onOpenEntity={onOpenEntity} onOpenTypedEntity={onOpenTypedEntity} />
      </section>

      <CompanyTimelinePanel
        timeline={timeline}
        loading={loading}
        error={error}
        retry={retry}
        note={dealCoverage?.note}
        onOpen={onOpen}
        onOpenEntity={onOpenEntity}
        onOpenTypedEntity={onOpenTypedEntity}
      />
    </div>
  );
}
