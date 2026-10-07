import { useQuery } from "@tanstack/react-query";
import { Check, ExternalLink, FileSearch, LocateFixed, Search } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import "../styles/knowledge.css";

import { EmptyState, ErrorState, Spinner } from "../components/common";
import { type EvidenceChunk, evidenceKeys, listEvidenceDatasets, searchEvidence } from "../lib/contracts/evidence";

export type EvidenceLocation = {
  query: string;
  datasetKeys: string[];
  documentId: string | null;
  chunkIndex: number | null;
};

function primitiveLocator(value: unknown): string | null {
  if (typeof value === "string") return value.trim().slice(0, 120) || null;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return null;
}

function sourceLocator(chunk: EvidenceChunk): string {
  const labels: Record<string, string> = {
    page: "页",
    page_number: "页",
    slide: "幻灯片",
    sheet: "工作表",
    row: "行",
    paragraph: "段落",
    section: "章节",
    line: "行",
  };
  const values: string[] = [];
  const add = (key: string, value: unknown) => {
    const normalized = primitiveLocator(value);
    if (!normalized) return;
    const label = labels[key] ?? key;
    const display = `${label} ${normalized}`;
    if (!values.includes(display)) values.push(display);
  };
  for (const position of chunk.positions) {
    if (!position || typeof position !== "object" || Array.isArray(position)) continue;
    const record = position as Record<string, unknown>;
    const locatorKind = primitiveLocator(record.locator_kind);
    const locatorValue = primitiveLocator(record.locator_value);
    if (locatorKind && locatorValue) add(locatorKind, locatorValue);
    for (const key of ["page", "page_number", "slide", "sheet", "row", "paragraph", "section", "line"]) {
      add(key, record[key]);
    }
    const startChar = primitiveLocator(record.start_char);
    const endChar = primitiveLocator(record.end_char);
    if (startChar && endChar) {
      const characterRange = `字符 ${startChar}-${endChar}`;
      if (!values.includes(characterRange)) values.push(characterRange);
    }
  }
  if (!values.length) {
    for (const key of ["page", "page_number", "slide", "sheet", "row", "paragraph", "section", "line"]) {
      add(key, chunk.metadata[key]);
    }
  }
  return values.slice(0, 4).join(" · ") || "来源未提供页码或段落定位";
}

function publicSourceUrl(chunk: EvidenceChunk): string | null {
  const value = chunk.metadata.source;
  if (typeof value !== "string") return null;
  try {
    const parsed = new URL(value);
    return ["http:", "https:"].includes(parsed.protocol) && !parsed.username && !parsed.password ? parsed.href : null;
  } catch {
    return null;
  }
}

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
          {expanded ? "收起完整引用" : "展开完整引用"}
        </button>
      ) : null}
    </blockquote>
  );
}

export function EvidenceView({
  initialQuery = "",
  initialDatasetKeys = [],
  initialDocumentId = null,
  initialChunkIndex = null,
  onLocationChange,
}: {
  initialQuery?: string;
  initialDatasetKeys?: string[];
  initialDocumentId?: string | null;
  initialChunkIndex?: number | null;
  onLocationChange?: (location: EvidenceLocation) => void;
}) {
  const controlled = Boolean(onLocationChange);
  const initialLocation = {
    query: initialQuery,
    datasetKeys: initialDatasetKeys,
    documentId: initialDocumentId,
    chunkIndex: initialChunkIndex,
  };
  const [query, setQuery] = useState(initialQuery);
  const [selectedDatasets, setSelectedDatasets] = useState<string[]>(initialDatasetKeys);
  const [localLocation, setLocalLocation] = useState<EvidenceLocation>(initialLocation);
  const initialDatasetSignature = initialDatasetKeys.join("\0");
  const location = controlled ? initialLocation : localLocation;
  const request = location.query.length >= 2 ? location : null;
  const datasets = useQuery({
    queryKey: evidenceKeys.datasets,
    queryFn: ({ signal }) => listEvidenceDatasets(signal),
  });
  const evidence = useQuery({
    queryKey: evidenceKeys.search(request?.query ?? "", request?.datasetKeys ?? []),
    queryFn: ({ signal }) => {
      if (!request) throw new Error("证据检索参数缺失");
      return searchEvidence({ query: request.query, datasetKeys: request.datasetKeys, signal });
    },
    enabled: request !== null,
  });

  useEffect(() => setQuery(initialQuery), [initialQuery]);
  useEffect(
    () => setSelectedDatasets(initialDatasetSignature ? initialDatasetSignature.split("\0") : []),
    [initialDatasetSignature],
  );

  function updateLocation(next: EvidenceLocation) {
    if (onLocationChange) onLocationChange(next);
    else setLocalLocation(next);
  }

  function toggle(key: string) {
    setSelectedDatasets((items) =>
      items.includes(key) ? items.filter((item) => item !== key) : [...items, key].sort(),
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = { query: query.trim(), datasetKeys: selectedDatasets, documentId: null, chunkIndex: null };
    if (
      location.query === next.query &&
      location.datasetKeys.join("\0") === next.datasetKeys.join("\0") &&
      location.documentId === null
    ) {
      void evidence.refetch();
    } else {
      updateLocation(next);
    }
  }

  function selectChunk(chunk: EvidenceChunk, chunkIndex: number) {
    updateLocation({
      query: location.query,
      datasetKeys: location.datasetKeys,
      documentId: chunk.document_id,
      chunkIndex,
    });
  }

  const result = evidence.data;
  const error = evidence.error instanceof Error ? evidence.error.message : "";
  const evidenceDomainsAvailable = Boolean(datasets.data?.length) && !datasets.error;
  const selectedChunk =
    result && location.chunkIndex !== null && location.chunkIndex >= 0 ? result.chunks[location.chunkIndex] : undefined;
  const validSelection = selectedChunk?.document_id === location.documentId ? selectedChunk : undefined;

  useEffect(() => {
    if (!validSelection || location.chunkIndex === null) return;
    const element = document.getElementById(`evidence-chunk-${location.chunkIndex + 1}`);
    element?.scrollIntoView?.({ block: "center" });
  }, [location.chunkIndex, validSelection]);

  return (
    <section className="evidence-workspace">
      <form className="evidence-query" onSubmit={submit}>
        <label>
          <span>研究问题或查证内容</span>
          <div className="query-input large">
            <Search size={19} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              minLength={2}
              required
              placeholder="输入靶点、活性值、专利号、试验号或项目事实"
            />
          </div>
        </label>
        <fieldset>
          <legend>证据域</legend>
          <div className="dataset-selector">
            {datasets.data?.map((dataset) => {
              const selected = selectedDatasets.includes(dataset.dataset_key);
              return (
                <button
                  key={dataset.dataset_key}
                  className={selected ? "selected" : ""}
                  type="button"
                  aria-pressed={selected}
                  title={dataset.attribution}
                  onClick={() => toggle(dataset.dataset_key)}
                >
                  <span className="check-box">{selected ? <Check size={13} /> : null}</span>
                  {dataset.display_name}
                </button>
              );
            })}
          </div>
          {datasets.isFetching && !datasets.data ? (
            <small className="evidence-field-help">正在加载已授权证据域</small>
          ) : null}
          {datasets.error ? (
            <button className="text-button" type="button" onClick={() => void datasets.refetch()}>
              证据域加载失败，重试
            </button>
          ) : null}
          {datasets.data?.length === 0 ? <small className="evidence-field-help">暂无可用证据域</small> : null}
          {datasets.data?.length ? <small className="evidence-field-help">不选择时检索全部已授权证据域</small> : null}
        </fieldset>
        <button
          className="primary-button"
          type="submit"
          disabled={evidence.isFetching || query.trim().length < 2 || !evidenceDomainsAvailable}
        >
          <FileSearch size={17} />
          查证原文
        </button>
      </form>
      <div className="evidence-results">
        {evidence.isFetching ? (
          <Spinner label="正在检索原始证据" />
        ) : error ? (
          <ErrorState message={error} retry={() => void evidence.refetch()} />
        ) : result ? (
          <>
            <div className="result-summary">
              <strong>{result.chunks.length}</strong>
              <span>个引用片段</span>
            </div>
            {location.documentId && !validSelection ? (
              <div className="evidence-stale-selection" role="alert">
                <span>该引用已不在当前检索结果中</span>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => updateLocation({ ...location, documentId: null, chunkIndex: null })}
                >
                  清除失效定位
                </button>
              </div>
            ) : null}
            {validSelection && location.chunkIndex !== null ? (
              <aside className="evidence-selection" aria-live="polite" aria-label="当前引用定位">
                <LocateFixed size={18} />
                <div>
                  <strong>{validSelection.document_name}</strong>
                  <span>
                    引用 {String(location.chunkIndex + 1).padStart(2, "0")} · {sourceLocator(validSelection)}
                  </span>
                </div>
              </aside>
            ) : null}
            {result.chunks.length ? (
              result.chunks.map((chunk, index) => {
                const active = Boolean(validSelection && location.chunkIndex === index);
                const dataset = datasets.data?.find((item) => item.dataset_key === chunk.dataset_id);
                const sourceUrl = publicSourceUrl(chunk);
                return (
                  <article
                    id={`evidence-chunk-${index + 1}`}
                    className={`evidence-record${active ? " active" : ""}`}
                    aria-current={active ? "true" : undefined}
                    key={`${chunk.document_id}-${JSON.stringify(chunk.positions)}-${chunk.content}`}
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
                          <dt>来源</dt>
                          <dd>{dataset?.display_name ?? "已授权资料"}</dd>
                        </div>
                        {dataset?.attribution ? (
                          <div>
                            <dt>来源说明</dt>
                            <dd>{dataset.attribution}</dd>
                          </div>
                        ) : null}
                        {sourceUrl ? (
                          <div>
                            <dt>原始资料</dt>
                            <dd>
                              <a href={sourceUrl} target="_blank" rel="noreferrer">
                                访问原始来源 <ExternalLink size={14} aria-hidden="true" />
                              </a>
                            </dd>
                          </div>
                        ) : null}
                      </dl>
                      <button className="secondary-button" type="button" onClick={() => selectChunk(chunk, index)}>
                        <LocateFixed size={15} />
                        {active ? "已定位此引用" : `定位引用 ${String(index + 1).padStart(2, "0")}`}
                      </button>
                    </div>
                  </article>
                );
              })
            ) : (
              <EmptyState title="未找到匹配证据" />
            )}
          </>
        ) : (
          <EmptyState title="等待查证" detail="检索结果将保留原文片段、文档来源和定位信息" />
        )}
      </div>
    </section>
  );
}
