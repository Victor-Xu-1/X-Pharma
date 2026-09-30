import { useQuery } from "@tanstack/react-query";
import { ExternalLink, FileSearch, X } from "lucide-react";

import { loadRecordProvenance, type ProvenanceSelection, provenanceKeys } from "../lib/contracts/provenance";
import { useModalFocus } from "../lib/useModalFocus";
import { EmptyState, ErrorState, formatDate, Spinner } from "./common";

function publicWarning(warning: string): string {
  if (/licen[cs]e|omitted fields?/i.test(warning)) return "部分技术字段因来源许可限制未展示。";
  if (/unavailable|not accessible|access denied/i.test(warning)) return "部分来源信息暂不可访问。";
  return "部分来源信息暂未展示。";
}

function publicAttribution(attribution: string | null | undefined): string {
  if (!attribution) return "授权来源";
  if (/tenant-provided source material/i.test(attribution)) return "用户提供的来源材料";
  return attribution;
}

export function RecordProvenanceDrawer({
  selection,
  onClose,
}: {
  selection: ProvenanceSelection;
  onClose: () => void;
}) {
  const dialogRef = useModalFocus<HTMLElement>(true, onClose);
  const provenance = useQuery({
    queryKey: provenanceKeys.record(selection.resourceType, selection.resourceId),
    queryFn: ({ signal }) => loadRecordProvenance(selection, signal),
  });

  const error = provenance.error instanceof Error ? provenance.error.message : "";
  return (
    <div className="drawer-backdrop" role="presentation">
      <button className="drawer-dismiss" type="button" aria-label="关闭证据面板" onClick={onClose} />
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
            <p className="eyebrow">来源与证据</p>
            <h2 id="provenance-title">原始证据</h2>
            <small>{selection.label}</small>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            title="关闭"
            aria-label="关闭原始证据"
            data-modal-autofocus="true"
          >
            <X size={18} />
          </button>
        </header>
        <div className="drawer-content">
          {provenance.isLoading ? <Spinner label="正在读取授权证据" /> : null}
          {error ? <ErrorState message={error} retry={() => void provenance.refetch()} /> : null}
          {[...new Set((provenance.data?.warnings ?? []).map(publicWarning))].map((warning) => (
            <p className="provenance-warning" key={warning}>
              {warning}
            </p>
          ))}
          {provenance.data && !provenance.data.items.length ? (
            <EmptyState title="暂无可展示证据" detail="该记录可能尚未关联公开来源，或来源暂不可访问" />
          ) : null}
          {provenance.data?.items.map((item) => (
            <article className="provenance-record" key={item.id}>
              <div className="provenance-record-head">
                <div>
                  <span className="record-kicker">来源记录</span>
                  <h3>{item.document_name || "文档名称受许可证限制"}</h3>
                </div>
              </div>
              {item.quote ? <blockquote>{item.quote}</blockquote> : <p>原文片段受许可证限制。</p>}
              <dl className="provenance-metadata">
                <div>
                  <dt>原文位置</dt>
                  <dd>{item.locator ?? "未标注"}</dd>
                </div>
                <div>
                  <dt>证据状态</dt>
                  <dd>{item.quote ? "已提供原文片段" : "原文片段受限"}</dd>
                </div>
              </dl>
              <footer>
                <span>{publicAttribution(item.license.attribution)}</span>
                <span>{formatDate(item.created_at, true)}</span>
                {item.source_uri ? (
                  <a href={item.source_uri} target="_blank" rel="noreferrer">
                    查看来源 <ExternalLink size={12} />
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
  return (
    <button
      className="icon-button"
      type="button"
      title="查看原始证据"
      aria-label={`查看 ${selection.label} 的原始证据`}
      onClick={() => onOpen(selection)}
    >
      <FileSearch size={17} />
    </button>
  );
}
