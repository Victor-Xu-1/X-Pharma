import { ArrowLeft, FileText } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { ResearchTabList } from "../../components/ResearchTabList";
import { SourceMetadata } from "../../components/SourceMetadata";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import { dealLabel, dealTypeLabels, directionLabels, formatAmount, statusLabels } from "../../lib/dealDisplay";
import type { DealSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { dealText as t } from "../../lib/i18n/deals";
import type { DealDossierSection } from "../../lib/workspaceRouting";
import type { DossierEntityOpener } from "../EntityDossierView";
import { DealAssets, DealParties } from "./DealPartiesAssets";
import { DealRights } from "./DealRights";

function DetailValue({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value || t("未披露")}</dd>
    </div>
  );
}

export function DealProfessionalDossier({
  data,
  loading,
  error,
  activeSection,
  onSectionChange,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenProvenance,
}: {
  data: DealSearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  activeSection: DealDossierSection;
  onSectionChange: (section: DealDossierSection, replace?: boolean) => void;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  useLocale();
  return (
    <section className="data-section deal-professional-page" aria-labelledby={data ? "deal-title" : undefined}>
      <button className="trial-back-button" type="button" onClick={onClose}>
        <ArrowLeft size={17} aria-hidden="true" />
        {t("返回交易列表")}
      </button>
      {!data && loading ? <Spinner label={t("正在加载交易专业档案")} /> : null}
      {error ? <ErrorState message={error.message || t("交易专业档案加载失败")} retry={onRetry} /> : null}
      {data && error ? (
        <p className="inline-feedback" role="status">
          {t("显示上次成功读取的交易详情；刷新未成功。")}
        </p>
      ) : null}
      {data && loading ? <Spinner label={t("正在刷新交易专业档案")} /> : null}
      {data ? (
        <>
          <header className="deal-professional-header">
            <div>
              <span>
                {t("交易专业档案 · {type} · {date}", {
                  type: dealLabel(data.deal_type, dealTypeLabels),
                  date: formatDate(data.announced_at),
                })}
              </span>
              <h2 id="deal-title">{data.name}</h2>
              <div className="trial-detail-status">
                <StatusBadge value={data.status} label={dealLabel(data.status, statusLabels)} />
                <span>{dealLabel(data.direction, directionLabels)}</span>
                <span>{data.territory ?? t("交易地域未披露")}</span>
              </div>
            </div>
          </header>
          <dl className="dossier-metrics deal-professional-metrics" aria-label={t("交易关键指标")}>
            <DetailValue term={t("交易状态")} value={dealLabel(data.status, statusLabels)} />
            <DetailValue term={t("参与方")} value={String(data.party_roles.length || data.party_entities.length)} />
            <DetailValue term={t("交易资产")} value={String(data.asset_stages.length || data.asset_entities.length)} />
            <DetailValue term={t("地域权益")} value={String(data.rights.length)} />
            <DetailValue term={t("首付款")} value={formatAmount(data.upfront_amount, data.currency)} />
            <DetailValue term={t("潜在总额")} value={formatAmount(data.total_potential_amount, data.currency)} />
          </dl>
          <ResearchTabList
            tabs={[
              { key: "overview", label: t("交易概览") },
              { key: "parties", label: t("参与方") },
              { key: "assets", label: t("资产与阶段") },
              { key: "rights", label: t("地域权益") },
              { key: "terms", label: t("条款与来源") },
            ]}
            activeTab={activeSection}
            onChange={onSectionChange}
            ariaLabel={t("交易专业档案分区")}
            idPrefix="deal-dossier"
            className="tab-bar trial-professional-tabs"
          />
          <div
            id={`deal-dossier-panel-${activeSection}`}
            role="tabpanel"
            aria-labelledby={`deal-dossier-tab-${activeSection}`}
            className="deal-professional-body"
          >
            {activeSection === "overview" ? (
              <section>
                <h3>{t("交易口径")}</h3>
                <dl className="trial-detail-grid">
                  <DetailValue term={t("状态")} value={dealLabel(data.status, statusLabels)} />
                  <DetailValue term={t("方向")} value={dealLabel(data.direction, directionLabels)} />
                  <DetailValue term={t("方向参照地区")} value={data.direction_reference_jurisdiction} />
                  <DetailValue term={t("初始披露")} value={formatDate(data.announced_at)} />
                  <DetailValue term={t("终止日期")} value={formatDate(data.terminated_at)} />
                  <DetailValue term={t("信息更新")} value={formatDate(data.source_updated_at)} />
                  <DetailValue term={t("首付款")} value={formatAmount(data.upfront_amount, data.currency)} />
                  <DetailValue term={t("潜在总额")} value={formatAmount(data.total_potential_amount, data.currency)} />
                </dl>
              </section>
            ) : null}
            {activeSection === "parties" ? <DealParties data={data} onOpenEntity={onOpenEntity} /> : null}
            {activeSection === "assets" ? <DealAssets data={data} onOpenEntity={onOpenEntity} /> : null}
            {activeSection === "rights" ? <DealRights data={data} onOpenEntity={onOpenEntity} /> : null}
            {activeSection === "terms" ? (
              <section>
                <h3>{t("披露条款与来源")}</h3>
                <SourceMetadata details={data.terms} />
                <dl className="trial-detail-grid">
                  <DetailValue term={t("源资料")} value={data.source_document_id ?? t("未关联")} />
                </dl>
              </section>
            ) : null}
            <section>
              <h3>{t("来源与证据")}</h3>
              <p className="regulatory-source-reference">
                <FileText size={15} aria-hidden="true" />
                {data.source_document_id ? t("来源文档 {id}", { id: data.source_document_id }) : t("来源文档未关联")}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "deal", resourceId: data.id, label: data.name }}
                onOpen={onOpenProvenance}
              />
            </section>
          </div>
        </>
      ) : null}
    </section>
  );
}
