import type { CompanyDossier } from "../lib/contracts/company";
import type { ProvenanceSelection } from "../lib/contracts/provenance";
import { useLocale } from "../lib/i18n";
import { companyDossierText as t } from "../lib/i18n/companyDossier";
import { Trials } from "./EntityDossierView";

/** A registry name is useful evidence, but is not a verified corporate portfolio. */
export function CompanySourceLabelOverview({
  data,
  onOpen,
  onOpenTrial,
  onOpenTrials,
}: {
  data: CompanyDossier;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenTrial: (trialId: string) => void;
  onOpenTrials: () => void;
}) {
  useLocale();
  const coverage = data.coverage.find((item) => item.domain === "clinical_trials");
  const total = coverage?.total ?? data.clinical_trials.length;
  const visibleTrials = data.clinical_trials.slice(0, 5);
  return (
    <section className="company-profile-section company-source-summary" aria-label={t("登记临床试验")}>
      <header>
        <h3>{t("登记临床试验（{total}）", { total })}</h3>
        <button type="button" onClick={onOpenTrials} disabled={!data.clinical_trials.length}>
          {t("全部登记试验")}
        </button>
      </header>
      <p>
        {t("本地已核验的注册关联，当前概览显示 {count} 项；不据此推断企业完整管线、资产所有权或批准用途。", {
          count: visibleTrials.length,
        })}
      </p>
      <Trials data={{ ...data, clinical_trials: visibleTrials }} onOpen={onOpen} onOpenTrial={onOpenTrial} />
    </section>
  );
}
