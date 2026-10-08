import { useQuery } from "@tanstack/react-query";
import { ExternalLink, FileSearch, X } from "lucide-react";

import { loadRecordProvenance, type ProvenanceSelection, provenanceKeys } from "../lib/contracts/provenance";
import { useLocale } from "../lib/i18n";
import { provenanceText as t } from "../lib/i18n/provenance";
import { useModalFocus } from "../lib/useModalFocus";
import { EmptyState, ErrorState, formatDate, Spinner } from "./common";

function publicWarning(warning: string): string {
  if (/licen[cs]e|omitted fields?/i.test(warning)) return t("部分技术字段因来源许可限制未展示。");
  if (/unavailable|not accessible|access denied/i.test(warning)) return t("部分来源信息暂不可访问。");
  return t("部分来源信息暂未展示。");
}

function publicAttribution(attribution: string | null | undefined): string {
  if (!attribution) return t("来源署名未提供");
  if (attribution.trim().toLowerCase() === "tenant-provided source material") return t("用户提供的来源材料");
  return attribution;
}

export function RecordProvenanceDrawer({
  selection,
  onClose,
}: {
  selection: ProvenanceSelection;
  onClose: () => void;
}) {
  useLocale();
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);
  const provenance = useQuery({
    queryKey: provenanceKeys.record(selection.resourceType, selection.resourceId),
    queryFn: ({ signal }) => loadRecordProvenance(selection, signal),
  });

  const error = provenance.error instanceof Error ? provenance.error.message : "";
  return (
    <div className="drawer-backdrop" role="presentation">
      <button className="drawer-dismiss" type="button" aria-label={t("关闭证据面板")} onClick={onClose} />
      <aside
        ref={dialogRef}
        className="detail-drawer provenance-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby="provenance-title"
        tabIndex={-1}
      >
        <header>
          <div>
            <p className="eyebrow">{t("来源与证据")}</p>
            <h2 id="provenance-title">{t("原始证据")}</h2>
            <small>{selection.label}</small>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            title={t("关闭")}
            aria-label={t("关闭原始证据")}
            data-modal-autofocus="true"
          >
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          {provenance.isLoading ? <Spinner label={t("正在读取授权证据")} /> : null}
          {error ? <ErrorState message={error} retry={() => void provenance.refetch()} /> : null}
          {[...new Set((provenance.data?.warnings ?? []).map(publicWarning))].map((warning) => (
            <p className="provenance-warning" key={warning}>
              {warning}
            </p>
          ))}
          {provenance.data && !provenance.data.items.length ? (
            <EmptyState title={t("暂无可展示证据")} detail={t("该记录可能尚未关联公开来源，或来源暂不可访问")} />
          ) : null}
          {provenance.data?.items.map((item) => (
            <article className="provenance-record" key={item.id}>
              <div className="provenance-record-head">
                <div>
                  <span className="record-kicker">{t("来源记录")}</span>
                  <h3>{item.document_name || t("文档名称未提供")}</h3>
                </div>
              </div>
              {item.quote ? <blockquote>{item.quote}</blockquote> : <p>{t("暂无可展示原文片段。")}</p>}
              <dl className="provenance-metadata">
                <div>
                  <dt>{t("原文位置")}</dt>
                  <dd>{item.locator ?? t("未标注")}</dd>
                </div>
                <div>
                  <dt>{t("证据状态")}</dt>
                  <dd>{item.quote ? t("已提供原文片段") : t("暂无可展示原文片段")}</dd>
                </div>
              </dl>
              <footer>
                <span>{publicAttribution(item.license.attribution)}</span>
                <span>{formatDate(item.created_at, true)}</span>
                {item.source_uri ? (
                  <a href={item.source_uri} target="_blank" rel="noreferrer">
                    {t("查看来源")} <ExternalLink size={12} />
                  </a>
                ) : null}
              </footer>
              {[...new Set((item.warnings ?? []).map(publicWarning))].map((warning) => (
                <small className="provenance-warning" key={warning}>
                  {warning}
                </small>
              ))}
            </article>
          ))}
        </div>
      </aside>
    </div>
  );
}

export function ProvenanceButton({
  selection,
  onOpen,
}: {
  selection: ProvenanceSelection;
  onOpen: (selection: ProvenanceSelection) => void;
}) {
  useLocale();
  return (
    <button
      className="icon-button"
      type="button"
      title={t("查看原始证据")}
      aria-label={t("查看 {label} 的原始证据", { label: selection.label })}
      onClick={() => onOpen(selection)}
    >
      <FileSearch size={17} />
    </button>
  );
}
