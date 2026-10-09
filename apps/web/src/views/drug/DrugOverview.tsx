import { Activity, Building2, Clock3, Dna, MapPin, ShieldCheck } from "lucide-react";
import { EmptyState, formatDate, StatusBadge } from "../../components/common";
import { DossierCoverageDisclosure } from "../../components/DossierCoverageDisclosure";
import { MoleculeDepiction } from "../../components/MoleculeDepiction";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import { localizedProgramModality as programModalityLabel } from "../../lib/i18n/programVocabulary";
import { publicCoverageNotice } from "../../lib/publicWarnings";
import type { DrugDossierSection } from "../../lib/workspaceRouting";
import { renderEntityLinks, uniqueProgramEntities } from "./associations";
import { coverageLabel, publicDrugCoverage } from "./coverage";
import type { DrugEntityOpener } from "./types";

export function DrugOverview({
  data,
  onOpenEntity,
  onOpenSection,
}: {
  data: DrugDossier;
  onOpenEntity: DrugEntityOpener;
  onOpenSection: (section: DrugDossierSection) => void;
}) {
  const targets = uniqueProgramEntities(data, "target");
  const indications = uniqueProgramEntities(data, "disease");
  const organizations = uniqueProgramEntities(data, "organization");
  const milestones = data.programs
    .flatMap((program) =>
      (program.milestones ?? []).map((milestone) => ({
        ...milestone,
        programId: program.id,
        drugName: program.drug_name,
      })),
    )
    .sort((left, right) => right.occurred_at.localeCompare(left.occurred_at))
    .slice(0, 5);
  const structure = data.structures[0];
  const coverageNotice = publicCoverageNotice(data.warnings);

  return (
    <div className="drug-profile-overview">
      <section className="drug-profile-section drug-profile-development">
        <header>
          <div>
            <span>{t("研发状态")}</span>
            <h3>{t("项目、靶点与适应症")}</h3>
          </div>
          <button type="button" onClick={() => onOpenSection("pipeline")} disabled={!data.programs.length}>
            {t("查看全部管线")}
          </button>
        </header>
        <dl className="drug-profile-attribute-strip">
          <div>
            <dt>
              <Activity size={15} />
              {t("药物类型")}
            </dt>
            <dd>{data.summary.modalities.map(programModalityLabel).join(t("、")) || t("未披露")}</dd>
          </div>
          <div>
            <dt>
              <Dna size={15} />
              {t("靶点")}
            </dt>
            <dd>{renderEntityLinks(targets, onOpenEntity)}</dd>
          </div>
          <div>
            <dt>
              <MapPin size={15} />
              {t("适应症")}
            </dt>
            <dd>{renderEntityLinks(indications, onOpenEntity)}</dd>
          </div>
          <div>
            <dt>
              <Building2 size={15} />
              {t("研发机构")}
            </dt>
            <dd>{renderEntityLinks(organizations, onOpenEntity)}</dd>
          </div>
        </dl>
      </section>

      <div className="drug-profile-overview-grid">
        <section className="drug-profile-section drug-profile-structure">
          <header>
            <div>
              <span>{t("化学结构")}</span>
              <h3>{t("主要结构")}</h3>
            </div>
            <button type="button" onClick={() => onOpenSection("structures")} disabled={!structure}>
              {t("查看结构")}
            </button>
          </header>
          {structure ? (
            <div className="drug-profile-structure-content">
              <MoleculeDepiction
                smiles={structure.isomeric_smiles ?? structure.canonical_smiles}
                name={data.entity.name}
              />
              <dl>
                <div>
                  <dt>InChIKey</dt>
                  <dd className="mono-cell">{structure.standard_inchi_key}</dd>
                </div>
                <div>
                  <dt>{t("分子式")}</dt>
                  <dd>{structure.molecular_formula ?? t("未披露")}</dd>
                </div>
                <div>
                  <dt>{t("分子量")}</dt>
                  <dd>{structure.molecular_weight ?? t("未披露")}</dd>
                </div>
              </dl>
            </div>
          ) : (
            <EmptyState title={t("暂无结构数据")} detail={t("当前数据中未收录可展示的化学结构")} />
          )}
        </section>

        <section className="drug-profile-section drug-profile-milestones">
          <header>
            <div>
              <span>{t("变化时间线")}</span>
              <h3>{t("最近研发里程碑")}</h3>
            </div>
            <Clock3 size={18} />
          </header>
          {milestones.length ? (
            <ol>
              {milestones.map((milestone) => (
                <li key={`${milestone.programId}-${milestone.milestone_type}-${milestone.occurred_at}`}>
                  <time>{formatDate(milestone.occurred_at)}</time>
                  <div>
                    <strong>{milestone.title}</strong>
                    <span>
                      {milestone.geography ?? t("地区未披露")} · {milestone.milestone_type}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
          ) : (
            <EmptyState title={t("暂无带日期的研发里程碑")} />
          )}
        </section>
      </div>

      <DossierCoverageDisclosure
        available={publicDrugCoverage(data).filter((item) => item.total > 0).length}
        total={data.coverage.length}
      >
        <section className="drug-profile-section drug-profile-coverage">
          <header>
            <div>
              <span>{t("数据概览")}</span>
              <h3>{t("各类信息收录情况")}</h3>
            </div>
            <time dateTime={data.as_of} title={t("本次档案查询时间，不代表所有来源的最后更新时间")}>
              {t("查询时间 {date}", { date: formatDate(data.as_of, true) })}
            </time>
          </header>
          <ScrollableTableRegion ariaLabel={t("药物档案领域数据覆盖")}>
            <table aria-label={t("药物档案领域数据覆盖")}>
              <thead>
                <tr>
                  <th>{t("信息类型")}</th>
                  <th>{t("收录数量")}</th>
                  <th>{t("状态")}</th>
                </tr>
              </thead>
              <tbody>
                {publicDrugCoverage(data).map((item) => (
                  <tr key={item.domain}>
                    <td>{coverageLabel(item.domain)}</td>
                    <td>{item.total}</td>
                    <td>
                      <StatusBadge value={item.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </ScrollableTableRegion>
          {coverageNotice ? (
            <p className="inline-alert">
              <ShieldCheck size={15} /> {coverageNotice}
            </p>
          ) : null}
        </section>
      </DossierCoverageDisclosure>
    </div>
  );
}
