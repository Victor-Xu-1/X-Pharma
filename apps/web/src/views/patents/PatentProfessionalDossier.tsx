import { ArrowLeft, FileText } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { PatentTimeline } from "../../components/PatentTimeline";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ResearchTabList } from "../../components/ResearchTabList";
import { ScrollableTableRegion } from "../../components/ScrollableTableRegion";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { entityLabels } from "../../lib/entityPresentation";
import type { PatentFamilySearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { patentText as t } from "../../lib/i18n/patents";
import { patentStatus } from "../../lib/patentDisplay";
import { sourceRecordRows } from "../../lib/sourceRecordRows";
import type { PatentDossierSection } from "../../lib/workspaceRouting";
import type { DossierEntityOpener } from "../EntityDossierView";
import { displayPatentList, patentCalendarDate } from "./presentation";

function DetailValue({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value || t("未披露")}</dd>
    </div>
  );
}

export function PatentProfessionalDossier({
  data,
  loading,
  error,
  activeSection,
  onSectionChange,
  onRetry,
  onClose,
  onOpenTypedEntity,
  onOpenProvenance,
}: {
  data: PatentFamilySearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  activeSection: PatentDossierSection;
  onSectionChange: (section: PatentDossierSection, replace?: boolean) => void;
  onRetry: () => void;
  onClose: () => void;
  onOpenTypedEntity: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  useLocale();
  const types = entityLabels();
  return (
    <section className="data-section patent-professional-page" aria-labelledby={data ? "patent-title" : undefined}>
      <button className="trial-back-button" type="button" onClick={onClose}>
        <ArrowLeft size={17} aria-hidden="true" />
        {t("返回专利族列表")}
      </button>
      {!data && loading ? <Spinner label={t("正在加载专利族详情")} /> : null}
      {error ? <ErrorState message={error.message || t("专利族详情加载失败")} retry={onRetry} /> : null}
      {data && error ? (
        <p className="inline-feedback" role="status">
          {t("显示上次成功读取的专利详情；刷新未成功。")}
        </p>
      ) : null}
      {data && loading ? <Spinner label={t("正在刷新专利族详情")} /> : null}
      {data ? (
        <>
          <header className="patent-professional-header">
            <div>
              <span>{t("专利族专业档案 · {identifier}", { identifier: data.family_identifier })}</span>
              <h2 id="patent-title">{data.title}</h2>
              <div className="trial-detail-status">
                <StatusBadge value={data.legal_status ?? ""} label={patentStatus(data.legal_status)} />
                <span>{t("优先权 {date}", { date: patentCalendarDate(data.priority_date) })}</span>
                <span>{t("预计到期 {date}", { date: patentCalendarDate(data.expiration_date) })}</span>
              </div>
            </div>
          </header>
          <dl className="dossier-metrics patent-professional-metrics" aria-label={t("专利族关键指标")}>
            <DetailValue term={t("法律状态")} value={patentStatus(data.legal_status)} />
            <DetailValue term={t("申请人")} value={String(data.applicants.length)} />
            <DetailValue term={t("公开文本")} value={String(data.publications.length)} />
            <DetailValue term={t("法律事件")} value={String(data.legal_events?.length ?? 0)} />
            <DetailValue term={t("独立权利要求")} value={String(data.independent_claims?.length ?? 0)} />
            <DetailValue term={t("关联资产")} value={String(data.linked_entities.length)} />
          </dl>
          <ResearchTabList
            tabs={[
              { key: "overview", label: t("专利族概览") },
              { key: "timeline", label: t("法律与权利要求") },
              { key: "relationships", label: t("关联资产") },
            ]}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel={t("专利族专业档案分区")}
            idPrefix="patent-dossier"
            className="tab-bar trial-professional-tabs"
          />
          <div
            id={`patent-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`patent-dossier-tab-${activeSection}`}
            className="patent-professional-body"
          >
            {activeSection === "overview" ? (
              <section>
                <h3>{t("专利族口径")}</h3>
                <dl className="trial-detail-grid">
                  <DetailValue
                    term={t("申请人")}
                    value={displayPatentList(data.applicants, t("未披露"), data.applicants.length)}
                  />
                  <DetailValue
                    term={t("发明人")}
                    value={displayPatentList(data.inventors, t("未披露"), data.inventors.length)}
                  />
                  <DetailValue term={t("法律状态日期")} value={formatDate(data.legal_status_at ?? "")} />
                </dl>
                {data.publications.length ? (
                  <ScrollableTableRegion className="pipeline-analysis-table-wrap" ariaLabel={t("公开文本")}>
                    <table className="pipeline-analysis-table" aria-label={t("公开文本")}>
                      <thead>
                        <tr>
                          <th scope="col">{t("公开号")}</th>
                          <th scope="col">{t("申请号")}</th>
                          <th scope="col">{t("辖区")}</th>
                          <th scope="col">{t("公开日期")}</th>
                          <th scope="col">{t("授权日期")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sourceRecordRows(data.publications).map(({ value: publication, key }) => (
                          <tr key={key}>
                            <th scope="row">{publication.publication_number}</th>
                            <td>{publication.application_number ?? "--"}</td>
                            <td>{publication.jurisdiction ?? "--"}</td>
                            <td>{patentCalendarDate(publication.publication_date)}</td>
                            <td>{patentCalendarDate(publication.grant_date)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </ScrollableTableRegion>
                ) : (
                  <p className="muted-value">{t("未披露")}</p>
                )}
              </section>
            ) : null}
            {activeSection === "timeline" ? (
              <section>
                <h3>{t("法律事件与独立权利要求")}</h3>
                <PatentTimeline patent={data} />
              </section>
            ) : null}
            {activeSection === "relationships" ? (
              <section>
                <h3>{t("关联实体")}</h3>
                <div className="deal-detail-list">
                  {data.linked_entities.length ? (
                    data.linked_entities.map((entity) => (
                      <button
                        key={entity.id}
                        type="button"
                        onClick={() => onOpenTypedEntity(entity.entity_type, entity.id)}
                      >
                        <strong>{entity.name}</strong>
                        <span>
                          {Object.hasOwn(types, entity.entity_type) ? types[entity.entity_type] : entity.entity_type}
                        </span>
                      </button>
                    ))
                  ) : (
                    <span>{t("暂无关联实体信息")}</span>
                  )}
                </div>
              </section>
            ) : null}
            <section>
              <h3>{t("来源与证据")}</h3>
              <p className="regulatory-source-reference">
                <FileText size={15} aria-hidden="true" />
                {data.source_document_id
                  ? t("来源文档 {identifier}", { identifier: data.source_document_id })
                  : t("来源文档未关联")}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "patent_family", resourceId: data.id, label: data.family_identifier }}
                onOpen={onOpenProvenance}
              />
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
