import { ExternalLink, LocateFixed } from "lucide-react";
import { useState } from "react";
import type { EvidenceChunk } from "../../lib/contracts/evidence";
import { publicSourceUrl, sourceLocator } from "../../lib/evidencePresentation";
import type { EvidenceDatasetRead } from "../../lib/generated";
import { useLocale } from "../../lib/i18n";
import { evidenceText as t } from "../../lib/i18n/evidence";

const EVIDENCE_PREVIEW_LIMIT = 720;

function EvidenceQuote({ content }: { content: string }) {
  const [expanded, setExpanded] = useState(false);
  const collapsible = content.length > EVIDENCE_PREVIEW_LIMIT;
  const visibleContent = !collapsible || expanded ? content : `${content.slice(0, EVIDENCE_PREVIEW_LIMIT).trimEnd()}…`;
  return (
    <blockquote style={{ overflowWrap: "anywhere", wordBreak: "break-word" }}>
      <span>{visibleContent}</span>
      {collapsible ? (
        <button
          className="text-button"
          type="button"
          aria-expanded={expanded}
          style={{ display: "block", marginTop: "8px" }}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? t("收起完整引用") : t("展开完整引用")}
        </button>
      ) : null}
    </blockquote>
  );
}

export function EvidenceRecord({
  chunk,
  index,
  active,
  dataset,
  onSelect,
}: {
  chunk: EvidenceChunk;
  index: number;
  active: boolean;
  dataset?: EvidenceDatasetRead;
  onSelect: () => void;
}) {
  useLocale();
  const sourceUrl = publicSourceUrl(chunk);
  return (
    <article
      id={`evidence-chunk-${index + 1}`}
      className={`evidence-record${active ? " active" : ""}`}
      aria-current={active ? "true" : undefined}
    >
      <div className="citation-index">{String(index + 1).padStart(2, "0")}</div>
      <div>
        <div className="evidence-head">
          <h3>{chunk.document_name}</h3>
        </div>
        <EvidenceQuote content={chunk.content} />
        <p className="evidence-locator">{sourceLocator(chunk)}</p>
        <dl>
          <div>
            <dt>{t("来源")}</dt>
            <dd>{dataset?.display_name ?? t("已授权资料")}</dd>
          </div>
          {dataset?.attribution ? (
            <div>
              <dt>{t("来源说明")}</dt>
              <dd>{dataset.attribution}</dd>
            </div>
          ) : null}
          {sourceUrl ? (
            <div>
              <dt>{t("原始资料")}</dt>
              <dd>
                <a href={sourceUrl} target="_blank" rel="noreferrer">
                  {t("访问原始来源")} <ExternalLink size={14} aria-hidden="true" />
                </a>
              </dd>
            </div>
          ) : null}
        </dl>
        <button className="secondary-button" type="button" onClick={onSelect}>
          <LocateFixed size={15} />
          {active ? t("已定位此引用") : t("定位引用 {number}", { number: String(index + 1).padStart(2, "0") })}
        </button>
      </div>
    </article>
  );
}
