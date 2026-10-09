import { Clock3, FlaskConical, ShieldCheck } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { DossierCoverageDisclosure } from "../../components/DossierCoverageDisclosure";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { CompanyDossier } from "../../lib/contracts/company";
import { useLocale } from "../../lib/i18n";
import { companyDossierText as t } from "../../lib/i18n/companyDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../../lib/i18n/programVocabulary";
import type { CompanyDossierSection } from "../../lib/workspaceRouting";
import { dossierDomainLabel as coverageLabel } from "../dossier/vocabulary";
import { AssetPortfolio } from "./AssetPortfolio";
export function CompanyOverview({
  data,
  onOpenDrug,
  onOpenSection,
}: {
  data: CompanyDossier;
  onOpenDrug: (drugId: string) => void;
  onOpenSection: (section: CompanyDossierSection) => void;
}) {
  useLocale();
  const phaseDistribution = data.summary.phase_distribution ?? {};
  const maximumPhaseCount = Math.max(1, ...Object.values(phaseDistribution));

  return (
    <div className="company-profile-overview">
      <div className="company-profile-overview-grid">
        <section className="company-profile-section">
          <header>
            <div>
              <h3>{t("研发阶段分布")}</h3>
            </div>
            <button type="button" onClick={() => onOpenSection("pipeline")} disabled={!data.programs.length}>
              {t("查看全部管线")}
            </button>
          </header>
          {Object.keys(phaseDistribution).length ? (
            <ol className="company-phase-distribution" aria-label={t("公司研发阶段分布")}>
              {Object.entries(phaseDistribution).map(([phase, count]) => (
                <li key={phase}>
                  <span>{phaseLabel(phase)}</span>
                  <div>
                    <i style={{ width: `${(count / maximumPhaseCount) * 100}%` }} />
                  </div>
                  <strong>{count}</strong>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title={t("暂无可统计研发阶段")} />
          )}
          <p className="company-modality-line">
            <FlaskConical size={15} />
            {(data.summary.modalities ?? []).join(t("、")) || t("当前未披露研发模态")}
          </p>
        </section>

        <AssetPortfolio data={data} onOpenDrug={onOpenDrug} />
      </div>

      <section className="company-profile-section">
        <header>
          <div>
            <h3>{t("最近公司事件")}</h3>
          </div>
          <button type="button" onClick={() => onOpenSection("timeline")} disabled={!data.timeline.items.length}>
            {t("完整时间线")}
          </button>
        </header>
        {data.timeline.items.length ? (
          <ol className="company-profile-recent-events">
            {data.timeline.items.slice(0, 5).map((event) => (
              <li key={event.id}>
                <Clock3 size={15} />
                <time>{formatDate(event.occurred_at)}</time>
                <strong>{event.title}</strong>
                <span>{event.event_type === "program_status" ? t("管线状态") : t("交易公告")}</span>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState title={t("暂无带日期的公司事件")} />
        )}
      </section>

      <DossierCoverageDisclosure
        available={data.coverage.filter((item) => item.total > 0).length}
        total={data.coverage.length}
      >
        <section className="company-profile-section company-profile-coverage">
          <header>
            <div>
              <h3>{t("领域数据覆盖")}</h3>
            </div>
            <time dateTime={data.as_of} title={t("本次档案查询时间，不代表所有来源的最后更新时间")}>
              {t("查询时间 {date}", { date: formatDate(data.as_of, true) })}
            </time>
          </header>
          <ScrollableTableRegion ariaLabel={t("公司档案领域数据覆盖")}>
            <table aria-label={t("公司档案领域数据覆盖")}>
              <thead>
                <tr>
                  <th>{t("领域")}</th>
                  <th>{t("总量")}</th>
                  <th>{t("本次返回")}</th>
                  <th>{t("状态")}</th>
                  <th>{t("说明")}</th>
                </tr>
              </thead>
              <tbody>
                {data.coverage.map((item) => (
                  <tr key={item.domain}>
                    <td>{coverageLabel(item.domain)}</td>
                    <td>{item.total}</td>
                    <td>{item.returned}</td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                    <td>{item.note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          {(data.warnings ?? []).map((warning) => (
            <p className="inline-alert" key={warning}>
              <ShieldCheck size={15} /> {warning}
            </p>
          ))}
        </section>
      </DossierCoverageDisclosure>
    </div>
  );
}
