import { FileText, X } from "lucide-react";
import { ErrorState, formatDate, Spinner, StatusBadge } from "../../components/common";
import { ProvenanceButton } from "../../components/RecordProvenanceDrawer";
import { SourceMetadata } from "../../components/SourceMetadata";
import type { ProvenanceSelection } from "../../lib/contracts/provenance";
import type { RegulatoryEventSearchItemRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { regulatoryText as t } from "../../lib/i18n/regulatory";
import {
  designationLabels,
  eventTypeLabels,
  labelChangeLabels,
  regulatoryStatusLabels,
  safetySignalLabels,
  safetyStatusLabels,
  severityLabels,
} from "../../lib/regulatoryDisplay";
import { useModalFocus } from "../../lib/useModalFocus";
import type { DossierEntityOpener } from "../EntityDossierView";
import { regulatoryValue as displayValue, regulatoryBoolean } from "./presentation";
export function RegulatoryDetailDrawer({
  data,
  loading,
  error,
  onRetry,
  onClose,
  onOpenEntity,
  onOpenTypedEntity,
  onOpenProvenance,
}: {
  data: RegulatoryEventSearchItemRead | undefined;
  loading: boolean;
  error: Error | null;
  onRetry: () => void;
  onClose: () => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTypedEntity?: DossierEntityOpener;
  onOpenProvenance: (selection: ProvenanceSelection) => void;
}) {
  useLocale();
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);

  return (
    <div className="drawer-backdrop" role="presentation">
      <button className="drawer-dismiss" type="button" aria-label={t("关闭监管事件详情")} onClick={onClose} />
      <aside
        ref={dialogRef}
        className="detail-drawer regulatory-detail-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="regulatory-event-title"
        tabIndex={-1}
      >
        <header className="deal-detail-header">
          <div>
            {data ? <span>{`${data.agency} · ${data.jurisdiction} · ${data.event_identifier}`}</span> : null}
            <h2 id="regulatory-event-title">{data?.title ?? t("监管事件详情")}</h2>
            {data ? (
              <div className="trial-detail-status">
                <StatusBadge value={displayValue(data.event_type, eventTypeLabels)} />
                <span>{formatDate(data.decision_date ?? "")}</span>
                <span>{displayValue(data.status, regulatoryStatusLabels)}</span>
              </div>
            ) : null}
          </div>
          <button
            className="icon-button"
            type="button"
            aria-label={t("关闭监管事件详情")}
            title={t("关闭")}
            data-modal-autofocus="true"
            onClick={onClose}
          >
            <X size={18} />
          </button>
        </header>
        {loading ? (
          <Spinner label={t("正在加载监管事件详情")} />
        ) : error ? (
          <ErrorState message={error.message || t("监管事件详情加载失败")} retry={onRetry} />
        ) : data ? (
          <div className="drawer-content deal-detail-content regulatory-detail-content">
            <section>
              <h3>{t("事件口径")}</h3>
              <dl className="trial-detail-grid">
                <DetailValue term={t("监管机构")} value={`${data.agency} / ${data.jurisdiction}`} />
                <DetailValue term={t("事件类型")} value={displayValue(data.event_type, eventTypeLabels)} />
                <DetailValue term={t("申请号")} value={data.application_number} />
                <DetailValue term={t("决定日期")} value={formatDate(data.decision_date ?? "")} />
                <DetailValue term={t("认定资格")} value={displayValue(data.designation_type, designationLabels)} />
                <DetailValue term={t("来源更新")} value={formatDate(data.source_updated_at ?? "", true)} />
              </dl>
            </section>
            <section>
              <h3>{t("标签与适用范围")}</h3>
              <dl className="trial-detail-grid">
                <DetailValue term={t("标签变更")} value={displayValue(data.label_change_type, labelChangeLabels)} />
                <DetailValue term={t("标签版本")} value={data.label_version} />
                <DetailValue term={t("生效日期")} value={formatDate(data.label_effective_at ?? "")} />
                <DetailValue term={t("批准人群")} value={data.approved_population} />
                <DetailValue term={t("治疗线次")} value={data.line_of_therapy} />
                <DetailValue term={t("生物标志物")} value={data.biomarker} />
                <DetailValue term={t("给药途径")} value={data.route_of_administration} />
                <DetailValue term={t("剂型")} value={data.dosage_form} />
                <DetailValue term={t("黑框警告")} value={regulatoryBoolean(data.has_boxed_warning)} />
              </dl>
            </section>
            <section>
              <h3>{t("安全信号与风险措施")}</h3>
              <dl className="trial-detail-grid">
                <DetailValue term={t("信号类型")} value={displayValue(data.safety_signal_type, safetySignalLabels)} />
                <DetailValue term={t("安全术语")} value={data.safety_term} />
                <DetailValue term={t("严重程度")} value={displayValue(data.safety_severity, severityLabels)} />
                <DetailValue term={t("信号状态")} value={displayValue(data.safety_status, safetyStatusLabels)} />
                <DetailValue term={t("影响人群")} value={data.affected_population} />
                <DetailValue term={t("识别日期")} value={formatDate(data.safety_identified_at ?? "")} />
                <DetailValue term={t("确认日期")} value={formatDate(data.safety_confirmed_at ?? "")} />
                <DetailValue term={t("解决日期")} value={formatDate(data.safety_resolved_at ?? "")} />
              </dl>
              <p className="regulatory-risk-actions">
                {data.risk_actions.length ? data.risk_actions.join("；") : t("风险措施未披露")}
              </p>
            </section>
            <section>
              <h3>{t("关联实体")}</h3>
              <div className="deal-detail-list">
                <button
                  type="button"
                  onClick={() => {
                    if (onOpenTypedEntity) {
                      onOpenTypedEntity(data.subject_entity.entity_type, data.subject_entity.id);
                      return;
                    }
                    onOpenEntity(data.subject_entity.id);
                  }}
                >
                  <strong>{data.subject_entity.name}</strong>
                  <span>{t("药物 / 产品")}</span>
                </button>
                {data.indication_entity ? (
                  <button
                    type="button"
                    onClick={() => {
                      const entityId = data.indication_entity?.id ?? "";
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(data.indication_entity?.entity_type ?? "disease", entityId);
                        return;
                      }
                      onOpenEntity(entityId);
                    }}
                  >
                    <strong>{data.indication_entity.name}</strong>
                    <span>{t("适应症")}</span>
                  </button>
                ) : (
                  <span>{t("适应症未关联")}</span>
                )}
                {data.organization_entity ? (
                  <button
                    type="button"
                    aria-label={t("打开 {name} 档案", { name: data.organization_entity.name })}
                    onClick={() => {
                      const entityId = data.organization_entity?.id ?? "";
                      if (onOpenTypedEntity) {
                        onOpenTypedEntity(data.organization_entity?.entity_type ?? "organization", entityId);
                        return;
                      }
                      onOpenEntity(entityId);
                    }}
                  >
                    <strong>{data.organization_entity.name}</strong>
                    <span>{t("申办方")}</span>
                  </button>
                ) : (
                  <span>{t("申办方未关联")}</span>
                )}
              </div>
            </section>
            <SourceMetadata details={data.details} />
            <section>
              <h3>{t("补充信息与来源")}</h3>
              <p className="regulatory-source-reference">
                <FileText size={15} />
                {data.source_document_id ? t("来源文档已关联") : t("来源文档未关联")}
              </p>
              <ProvenanceButton
                selection={{ resourceType: "regulatory_event", resourceId: data.id, label: data.title }}
                onOpen={onOpenProvenance}
              />
            </section>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
export function DetailValue({ term, value }: { term: string; value: string | null | undefined }) {
  return (
    <div>
      <dt>{term}</dt>
      <dd>{value || t("未披露")}</dd>
    </div>
  );
}
