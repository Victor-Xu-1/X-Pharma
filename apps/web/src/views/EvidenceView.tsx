import { useQuery } from "@tanstack/react-query";
import { Check, FileSearch, LocateFixed, Search } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import "../styles/knowledge.css";

import { EmptyState, ErrorState, Spinner } from "../components/common";
import { type EvidenceChunk, evidenceKeys, listEvidenceDatasets, searchEvidence } from "../lib/contracts/evidence";
import { sourceLocator } from "../lib/evidencePresentation";
import { useLocale } from "../lib/i18n";
import { evidenceText as t } from "../lib/i18n/evidence";
import { EvidenceRecord } from "./evidence/EvidenceRecord";

export type EvidenceLocation = {
  query: string;
  datasetKeys: string[];
  documentId: string | null;
  chunkIndex: number | null;
};

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
  useLocale();
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
      if (!request) throw new Error(t("证据检索参数缺失"));
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
          <span>{t("研究问题或查证内容")}</span>
          <div className="query-input large">
            <Search size={19} />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              minLength={2}
              required
              placeholder={t("输入靶点、活性值、专利号、试验号或项目事实")}
            />
          </div>
        </label>
        <fieldset>
          <legend>{t("证据域")}</legend>
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
            <small className="evidence-field-help">{t("正在加载已授权证据域")}</small>
          ) : null}
          {datasets.error ? (
            <button className="text-button" type="button" onClick={() => void datasets.refetch()}>
              {t("证据域加载失败，重试")}
            </button>
          ) : null}
          {datasets.data?.length === 0 ? <small className="evidence-field-help">{t("暂无可用证据域")}</small> : null}
          {datasets.data?.length ? (
            <small className="evidence-field-help">{t("不选择时检索全部已授权证据域")}</small>
          ) : null}
        </fieldset>
        <button
          className="primary-button"
          type="submit"
          disabled={evidence.isFetching || query.trim().length < 2 || !evidenceDomainsAvailable}
        >
          <FileSearch size={17} />
          {t("查证原文")}
        </button>
      </form>
      <div className="evidence-results">
        {evidence.isFetching ? (
          <Spinner label={t("正在检索原始证据")} />
        ) : error ? (
          <ErrorState message={error} retry={() => void evidence.refetch()} />
        ) : result ? (
          <>
            <div className="result-summary">
              <strong>{result.chunks.length}</strong>
              <span>{t("个引用片段")}</span>
            </div>
            {location.documentId && !validSelection ? (
              <div className="evidence-stale-selection" role="alert">
                <span>{t("该引用已不在当前检索结果中")}</span>
                <button
                  className="secondary-button"
                  type="button"
                  onClick={() => updateLocation({ ...location, documentId: null, chunkIndex: null })}
                >
                  {t("清除失效定位")}
                </button>
              </div>
            ) : null}
            {validSelection && location.chunkIndex !== null ? (
              <aside className="evidence-selection" aria-live="polite" aria-label={t("当前引用定位")}>
                <LocateFixed size={18} />
                <div>
                  <strong>{validSelection.document_name}</strong>
                  <span>
                    {t("引用 {number} · {locator}", {
                      number: String(location.chunkIndex + 1).padStart(2, "0"),
                      locator: sourceLocator(validSelection),
                    })}
                  </span>
                </div>
              </aside>
            ) : null}
            {result.chunks.length ? (
              result.chunks.map((chunk, index) => (
                <EvidenceRecord
                  key={`${chunk.document_id}-${JSON.stringify(chunk.positions)}-${chunk.content}`}
                  chunk={chunk}
                  index={index}
                  active={Boolean(validSelection && location.chunkIndex === index)}
                  dataset={datasets.data?.find((item) => item.dataset_key === chunk.dataset_id)}
                  onSelect={() => selectChunk(chunk, index)}
                />
              ))
            ) : (
              <EmptyState title={t("未找到匹配证据")} />
            )}
          </>
        ) : (
          <EmptyState title={t("等待查证")} detail={t("检索结果将保留原文片段、文档来源和定位信息")} />
        )}
      </div>
    </section>
  );
}
