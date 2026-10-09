import { Activity, Dna, ShieldCheck } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { DossierCoverageDisclosure } from "../../components/DossierCoverageDisclosure";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DiseaseDossier } from "../../lib/contracts/disease";
import { useLocale } from "../../lib/i18n";
import { diseaseDossierText as t } from "../../lib/i18n/diseaseDossier";
import { localizedFullDevelopmentPhase as phaseLabel } from "../../lib/i18n/programVocabulary";
import type { DiseaseDossierSection } from "../../lib/workspaceRouting";
import { dossierDomainLabel as coverageLabel } from "../dossier/vocabulary";
import type { DossierEntityOpener } from "../EntityDossierView";
import { EpidemiologyTable } from "./EpidemiologyTable";

export function DiseaseOverview({
  data,
  onOpenTypedEntity,
  onOpenSection,
  onOpenEpidemiology,
}: {
  data: DiseaseDossier;
  onOpenTypedEntity: DossierEntityOpener;
  onOpenSection: (section: DiseaseDossierSection) => void;
  onOpenEpidemiology: (diseaseId: string) => void;
}) {
  useLocale();
  const phaseDistribution = data.summary.phase_distribution ?? {};
  const maximumPhaseCount = Math.max(1, ...Object.values(phaseDistribution));
  const targets = Array.from(
    new Map([
      ...data.programs.flatMap((program) =>
        (program.targets?.length
          ? program.targets
          : [{ entity_id: program.target_entity_id, name: program.target_name }]
        )
          .filter((target) => target.entity_id && target.name)
          .map((target) => [target.entity_id as string, target.name as string] as const),
      ),
      ...data.target_evidence.map((item) => [item.target_entity_id, item.target_name] as const),
    ]).entries(),
  );

  return (
    <div className="company-profile-overview disease-profile-overview">
      <div className="company-profile-overview-grid">
        <section className="company-profile-section">
          <header>
            <div>
              <h3>{t("研发阶段分布")}</h3>
            </div>
            <button type="button" onClick={() => onOpenSection("pipeline")} disabled={!data.programs.length}>
              {t("查看研发格局")}
            </button>
          </header>
          {Object.keys(phaseDistribution).length ? (
            <ol className="company-phase-distribution" aria-label={t("疾病研发阶段分布")}>
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
            <Activity size={15} />
            {(data.summary.modalities ?? []).join(t("、")) || t("当前未披露研发模态")}
          </p>
        </section>

        <section className="company-profile-section">
          <header>
            <div>
              <h3>{t("关键关联靶点")}</h3>
            </div>
            <Dna size={18} />
          </header>
          {targets.length ? (
            <>
              <ol className="company-asset-list">
                {targets.slice(0, 10).map(([id, name]) => (
                  <li key={id}>
                    <button type="button" onClick={() => onOpenTypedEntity("target", id)}>
                      {name}
                    </button>
                    <span>{t("关联靶点")}</span>
                  </li>
                ))}
              </ol>
              {targets.length > 10 ? (
                <details className="disease-target-disclosure">
                  <summary>{t("更多关联靶点（{count}）", { count: targets.length - 10 })}</summary>
                  <ol className="company-asset-list">
                    {targets.slice(10).map(([id, name]) => (
                      <li key={id}>
                        <button type="button" onClick={() => onOpenTypedEntity("target", id)}>
                          {name}
                        </button>
                        <span>{t("关联靶点")}</span>
                      </li>
                    ))}
                  </ol>
                </details>
              ) : null}
            </>
          ) : (
            <EmptyState title={t("暂无关联靶点")} />
          )}
        </section>
      </div>

      <section className="company-profile-section">
        <header>
          <div>
            <h3>{t("最新疾病负担观测")}</h3>
          </div>
          <button type="button" onClick={() => onOpenEpidemiology(data.entity.id)} disabled={!data.epidemiology.total}>
            {t("进入流行病学数据库")}
          </button>
        </header>
        <EpidemiologyTable items={data.epidemiology.items.slice(0, 5)} onOpen={() => undefined} compact />
      </section>

      <DossierCoverageDisclosure
        available={data.coverage.filter((item) => item.total > 0).length + Number(data.epidemiology.total > 0)}
        total={data.coverage.length + 1}
      >
        <section className="company-profile-section company-profile-coverage">
          <header>
            <div>
              <h3>{t("领域数据覆盖")}</h3>
            </div>
            <time dateTime={data.as_of} title={t("本次档案查询时间不代表所有来源的最后更新时间")}>
              {t("查询时间 {date}", { date: formatDate(data.as_of, true) })}
            </time>
          </header>
          <ScrollableTableRegion ariaLabel={t("疾病档案领域数据覆盖")}>
            <table aria-label={t("疾病档案领域数据覆盖")}>
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
                <tr>
                  <td>{t("流行病学")}</td>
                  <td>{data.epidemiology.total}</td>
                  <td>{data.epidemiology.items.length}</td>
                  <td>
                    <StatusBadge value={data.epidemiology.total ? "available" : "empty"} />
                  </td>
                  <td>{t("疾病人群地区和统计口径下的观测数据")}</td>
                </tr>
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
          {data.warnings?.map((warning) => (
            <p className="inline-alert" key={warning}>
              <ShieldCheck size={15} /> {warning}
            </p>
          ))}
        </section>
      </DossierCoverageDisclosure>
    </div>
  );
}
