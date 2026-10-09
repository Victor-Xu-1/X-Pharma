import { Building2, MapPin } from "lucide-react";
import { EmptyState, ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ResultPagination } from "../../components/ResultPagination";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { DrugDossier } from "../../lib/contracts/drugDossier";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { controlledDossierLabel as controlledDrugLabel } from "../../lib/i18n/dossierVocabulary";
import { drugDossierText as t } from "../../lib/i18n/drugDossier";
import {
  localizedFullDevelopmentPhase as phaseLabel,
  localizedProgramModality as programModalityLabel,
  localizedProgramTag as programTagLabel,
} from "../../lib/i18n/programVocabulary";
import { publicProgramTags } from "../../lib/programDisplay";
import { ProgramIndicationLinks } from "./ProgramIndicationLinks";
import { ProgramOrganizationLinks } from "./ProgramOrganizationLinks";
import { ProgramProgressHistory } from "./ProgramProgressHistory";
import { ProgramTargetLinks } from "./ProgramTargetLinks";
import { geographyLabel, governedValue, listRegions, listValues } from "./programPresentation";
import type { DrugEntityOpener } from "./types";
import { drugCategoryLabels, innovationTypeLabels, programStatusLabels } from "./vocabulary";

export function DrugDevelopmentPortfolio({
  data,
  programs,
  totalPrograms,
  offset,
  pageSize,
  loading,
  fetching,
  error,
  onRetry,
  onPageChange,
  onOpen,
  onOpenEntity,
}: {
  data: DrugDossier;
  programs: DrugDossier["programs"];
  totalPrograms: number;
  offset: number;
  pageSize: number;
  loading: boolean;
  fetching: boolean;
  error: unknown;
  onRetry: () => void;
  onPageChange: (offset: number) => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: DrugEntityOpener;
}) {
  const errorMessage = error instanceof Error ? error.message : t("研发管线分页加载失败");
  if (loading && !programs.length) return <Spinner label={t("正在加载完整研发管线")} />;
  if (error && !programs.length) return <ErrorState message={errorMessage} retry={onRetry} />;
  if (!programs.length)
    return (
      <>
        <EmptyState
          title={t(totalPrograms > 0 ? "当前页没有研发项目" : "暂无关联研发管线")}
          detail={totalPrograms > 0 ? t("返回有效页查看已有项目") : undefined}
        />
        {totalPrograms > 0 ? (
          <ResultPagination
            totalRows={totalPrograms}
            offset={offset}
            pageSize={pageSize}
            onPageChange={onPageChange}
            ariaLabel={t("药物研发管线分页")}
          />
        ) : null}
      </>
    );
  return (
    <div className="drug-development-view">
      {error ? (
        <p className="domain-pagination-error" role="alert">
          {t("完整研发管线分页加载失败，当前显示已加载内容。")}
          <span>{errorMessage}</span>
          <button className="text-button" type="button" onClick={onRetry}>
            {t("重试")}
          </button>
        </p>
      ) : null}
      <section className="drug-profile-section" aria-labelledby="drug-indication-progress-title">
        <header>
          <div>
            <span>{t("适应症与地域")}</span>
            <h3 id="drug-indication-progress-title">{t("适应症与地区进度（{count}）", { count: totalPrograms })}</h3>
          </div>
          <MapPin size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel={t("药物适应症与地区进度")} className="drug-program-progress-region">
          <table aria-label={t("药物适应症与地区进度")}>
            <thead>
              <tr>
                <th>{t("适应症")}</th>
                <th>{t("全球阶段")}</th>
                <th>{t("中国阶段")}</th>
                <th>{t("记录地区")}</th>
                <th>{t("项目状态")}</th>
                <th>{t("靶点与机制")}</th>
                <th>{t("最新更新")}</th>
                <th aria-label={t("来源")} />
              </tr>
            </thead>
            <tbody>
              {programs.map((program) => (
                <tr key={program.id}>
                  <td>
                    <ProgramIndicationLinks program={program} onOpenEntity={onOpenEntity} />
                    {program.therapeutic_area ? (
                      <small className="cell-subtitle">{program.therapeutic_area}</small>
                    ) : null}
                  </td>
                  <td>
                    <strong>{phaseLabel(program.global_phase)}</strong>
                    <small className="cell-subtitle">
                      {program.global_phase_started_at
                        ? t("始于 {date}", { date: formatDate(program.global_phase_started_at) })
                        : t("起始日未披露")}
                    </small>
                  </td>
                  <td>
                    <strong>{phaseLabel(program.china_phase)}</strong>
                    <small className="cell-subtitle">
                      {program.china_phase_started_at
                        ? t("始于 {date}", { date: formatDate(program.china_phase_started_at) })
                        : t("起始日未披露")}
                    </small>
                  </td>
                  <td>{geographyLabel(program.geography)}</td>
                  <td>
                    <StatusBadge
                      value={program.program_status ?? "unknown"}
                      label={controlledDrugLabel(program.program_status ?? "unknown", programStatusLabels)}
                    />
                    {program.status_detail ? <small className="cell-subtitle">{program.status_detail}</small> : null}
                  </td>
                  <td>
                    <ProgramTargetLinks program={program} onOpenEntity={onOpenEntity} />
                    <small className="cell-subtitle">{program.mechanism_of_action ?? t("机制未披露")}</small>
                  </td>
                  <td>{formatDate(program.status_date)}</td>
                  <td>
                    <ProvenanceButton
                      selection={{
                        resourceType: "development_program",
                        resourceId: program.id,
                        label: program.disease_name ?? data.entity.name,
                      }}
                      onOpen={onOpen}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>

      <section className="drug-profile-section" aria-labelledby="drug-organization-rights-title">
        <header>
          <div>
            <span>{t("开发与商业化")}</span>
            <h3 id="drug-organization-rights-title">{t("研发机构与权益（{count}）", { count: totalPrograms })}</h3>
          </div>
          <Building2 size={18} aria-hidden="true" />
        </header>
        <ScrollableTableRegion ariaLabel={t("药物研发机构与权益")} className="drug-program-rights-region">
          <table aria-label={t("药物研发机构与权益")}>
            <thead>
              <tr>
                <th>{t("适应症")}</th>
                <th>{t("研发机构与角色")}</th>
                <th>{t("研发权益")}</th>
                <th>{t("商业化权益")}</th>
                <th>{t("药物类型与分类")}</th>
                <th>{t("项目标签")}</th>
                <th>{t("阶段历史与里程碑")}</th>
                <th aria-label={t("来源")} />
              </tr>
            </thead>
            <tbody>
              {programs.map((program) => (
                <tr key={program.id}>
                  <td>
                    <ProgramIndicationLinks program={program} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>
                    <ProgramOrganizationLinks program={program} onOpenEntity={onOpenEntity} />
                  </td>
                  <td>{listRegions(program.development_rights_regions)}</td>
                  <td>{listRegions(program.commercialization_rights_regions)}</td>
                  <td>
                    {program.modality ? programModalityLabel(program.modality) : t("未披露")}
                    <small className="cell-subtitle">
                      {listValues(
                        [
                          governedValue(program.innovation_type, innovationTypeLabels),
                          governedValue(program.drug_category, drugCategoryLabels),
                        ].filter((value): value is string => Boolean(value)),
                      )}
                    </small>
                  </td>
                  <td>{listValues(publicProgramTags(program.program_tags).map(programTagLabel))}</td>
                  <td>
                    <ProgramProgressHistory program={program} />
                  </td>
                  <td>
                    <ProvenanceButton
                      selection={{
                        resourceType: "development_program",
                        resourceId: program.id,
                        label: program.disease_name ?? data.entity.name,
                      }}
                      onOpen={onOpen}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </ScrollableTableRegion>
      </section>
      <ResultPagination
        totalRows={totalPrograms}
        offset={offset}
        pageSize={pageSize}
        onPageChange={onPageChange}
        notice={fetching ? t("正在更新研发管线…") : undefined}
        ariaLabel={t("药物研发管线分页")}
      />
    </div>
  );
}
