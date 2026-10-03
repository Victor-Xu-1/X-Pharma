import { useQuery } from "@tanstack/react-query";
import { ArrowUpRight, BookmarkPlus, Check, Code2, Copy, PencilLine, Search } from "lucide-react";
import { Component, type FormEvent, lazy, type ReactNode, Suspense, useCallback, useEffect, useState } from "react";

import { EmptyState, formatDate, Spinner } from "../components/common";
import { MoleculeDepiction } from "../components/MoleculeDepiction";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import {
  type ChemistrySearchHit,
  type ChemistrySearchInput,
  type ChemistrySearchMode,
  chemistryKeys,
  saveChemistrySearch,
  searchChemistry,
} from "../lib/contracts/chemistry";
import type { SavedSearchRead } from "../lib/generated";

const modeLabels: Record<ChemistrySearchMode, string> = {
  exact: "精确匹配",
  substructure: "子结构",
  similarity: "相似结构",
};

const chemistrySearchErrorMessages: Record<string, string> = {
  invalid_smiles: "无法识别该 SMILES，请检查结构式后重试",
  invalid_smarts: "无法识别该 SMARTS，请检查子结构表达式后重试",
};

function chemistrySearchErrorMessage(error: unknown): string {
  if (!error) return "";
  if (error instanceof Error) {
    try {
      const payload = JSON.parse(error.message) as {
        code?: unknown;
        detail?: { code?: unknown };
      };
      const code = typeof payload.code === "string" ? payload.code : payload.detail?.code;
      const message = typeof code === "string" ? chemistrySearchErrorMessages[code] : undefined;
      if (message) return message;
    } catch {
      // Fall through to the public-safe message for transport and unexpected server errors.
    }
  }
  return "结构检索暂时不可用，请稍后重试";
}

const StructureEditor = lazy(() =>
  import("../components/StructureEditor").then((module) => ({ default: module.StructureEditor })),
);

class StructureEditorBoundary extends Component<{ children: ReactNode; onFallback: () => void }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="structure-editor-fallback" role="alert">
          <strong>结构画板加载失败</strong>
          <button className="secondary-button" type="button" onClick={this.props.onFallback}>
            改用高级输入
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export function ChemistryView({
  onInspectEntity,
  initialSearch,
  savedSearchId = null,
  onSearchCommit,
  onSavedSearch,
}: {
  onInspectEntity: (entityId: string) => void;
  initialSearch?: ChemistrySearchInput | null;
  savedSearchId?: string | null;
  onSearchCommit?: () => void;
  onSavedSearch?: (savedSearch: SavedSearchRead) => void;
}) {
  const [mode, setMode] = useState<ChemistrySearchMode>("exact");
  const [inputMode, setInputMode] = useState<"draw" | "text">("draw");
  const [editorActive, setEditorActive] = useState(false);
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.7);
  const [limit, setLimit] = useState(20);
  const [validationError, setValidationError] = useState("");
  const [request, setRequest] = useState<{
    mode: ChemistrySearchMode;
    query: string;
    threshold: number;
    limit: number;
  } | null>(null);
  const [hydratedSavedSearchId, setHydratedSavedSearchId] = useState<string | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState("");
  const [shared, setShared] = useState(false);
  const [savePending, setSavePending] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [saveMessage, setSaveMessage] = useState("");
  const search = useQuery({
    queryKey: chemistryKeys.search(request),
    queryFn: ({ signal }) => {
      if (!request) throw new Error("结构检索参数缺失");
      return searchChemistry(request, signal);
    },
    enabled: request !== null,
  });
  const result = search.error ? undefined : search.data;
  const error = validationError || chemistrySearchErrorMessage(search.error);
  const busy = search.isFetching;
  const canSave = Boolean(request && result && !busy);

  useEffect(() => {
    if (!initialSearch || !savedSearchId || hydratedSavedSearchId === savedSearchId) return;
    setMode(initialSearch.mode);
    setInputMode("text");
    setEditorActive(false);
    setQuery(initialSearch.query);
    setThreshold(initialSearch.threshold ?? 0.7);
    setLimit(initialSearch.limit ?? 20);
    setValidationError("");
    setSaveMessage("");
    setRequest({
      mode: initialSearch.mode,
      query: initialSearch.query,
      threshold: initialSearch.threshold ?? 0.7,
      limit: initialSearch.limit ?? 20,
    });
    setHydratedSavedSearchId(savedSearchId);
  }, [hydratedSavedSearchId, initialSearch, savedSearchId]);

  const invalidateCommittedSearch = useCallback(() => {
    setRequest(null);
    setValidationError("");
    setSaveMessage("");
  }, []);
  const changeQuery = useCallback(
    (nextQuery: string) => {
      setQuery(nextQuery);
      invalidateCommittedSearch();
    },
    [invalidateCommittedSearch],
  );
  const applyEditorStructure = useCallback(
    (structure: string) => {
      changeQuery(structure);
    },
    [changeQuery],
  );
  const handleEditorError = useCallback((message: string) => {
    setRequest(null);
    setSaveMessage("");
    setValidationError(message);
  }, []);
  const changeInputMode = useCallback(
    (nextInputMode: "draw" | "text") => {
      const hadError = Boolean(validationError || search.error);
      setInputMode(nextInputMode);
      invalidateCommittedSearch();
      if (nextInputMode === "draw" && hadError) setQuery("");
    },
    [invalidateCommittedSearch, search.error, validationError],
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    const normalizedQuery = query.trim();
    if (!normalizedQuery) {
      setValidationError("请输入结构查询");
      return;
    }
    setValidationError("");
    const next = { mode, query: normalizedQuery, threshold, limit };
    if (
      request?.mode === next.mode &&
      request.query === next.query &&
      request.threshold === next.threshold &&
      request.limit === next.limit
    ) {
      void search.refetch();
    } else {
      setRequest(next);
    }
    setSaveMessage("");
    onSearchCommit?.();
  }

  function openSaveDialog() {
    if (!request || !result) return;
    setSaveName(`${modeLabels[request.mode]}结构检索`);
    setShared(false);
    setSaveError("");
    setSaveMessage("");
    setSaveOpen(true);
  }

  async function saveSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!request || !result || !saveName.trim()) return;
    setSavePending(true);
    setSaveError("");
    try {
      const saved = await saveChemistrySearch({ name: saveName.trim(), input: request, shared });
      setSaveOpen(false);
      setSaveMessage("结构检索已保存，可通过当前链接恢复");
      onSavedSearch?.(saved);
    } catch (caught) {
      setSaveError(caught instanceof Error ? caught.message : "结构检索保存失败");
    } finally {
      setSavePending(false);
    }
  }

  return (
    <section className="chemistry-workbench">
      <div className="chemistry-query">
        <div className="chemistry-query-head">
          <fieldset className="mode-control">
            <legend>检索模式</legend>
            <div>
              {(Object.keys(modeLabels) as ChemistrySearchMode[]).map((item) => (
                <button
                  key={item}
                  type="button"
                  className={mode === item ? "active" : ""}
                  aria-pressed={mode === item}
                  onClick={() => {
                    if (item === mode) return;
                    setMode(item);
                    invalidateCommittedSearch();
                  }}
                >
                  {modeLabels[item]}
                </button>
              ))}
            </div>
          </fieldset>
          <div className="structure-input-tabs" role="tablist" aria-label="结构输入方式">
            <button
              type="button"
              role="tab"
              aria-selected={inputMode === "draw"}
              className={inputMode === "draw" ? "active" : ""}
              onClick={() => {
                changeInputMode("draw");
                setEditorActive(true);
              }}
            >
              <PencilLine size={16} />
              绘制结构
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={inputMode === "text"}
              className={inputMode === "text" ? "active" : ""}
              onClick={() => changeInputMode("text")}
            >
              <Code2 size={16} />
              高级输入
            </button>
          </div>
        </div>

        {inputMode === "draw" && !editorActive ? (
          <section className="structure-editor-gate" aria-label="结构画板">
            <PencilLine size={22} aria-hidden="true" />
            <strong>结构画板尚未打开</strong>
            <button className="primary-button" type="button" onClick={() => setEditorActive(true)}>
              <PencilLine size={16} />
              打开结构画板
            </button>
          </section>
        ) : inputMode === "draw" ? (
          <StructureEditorBoundary onFallback={() => changeInputMode("text")}>
            <Suspense
              fallback={
                <div className="structure-editor-loading">
                  <Spinner label="正在加载结构画板" />
                </div>
              }
            >
              <StructureEditor
                value={query}
                format={mode === "substructure" ? "smarts" : "smiles"}
                onApply={applyEditorStructure}
                onError={handleEditorError}
              />
            </Suspense>
          </StructureEditorBoundary>
        ) : (
          <label className="structure-query-input">
            <span>{mode === "substructure" ? "SMARTS" : "SMILES"}</span>
            <textarea
              rows={4}
              value={query}
              onChange={(event) => {
                changeQuery(event.target.value);
              }}
              placeholder={mode === "substructure" ? "输入 SMARTS" : "输入 SMILES"}
              maxLength={20_000}
              spellCheck={false}
            />
          </label>
        )}

        <form className="chemistry-options" onSubmit={submit}>
          {mode === "similarity" ? (
            <label className="threshold-control">
              <span>
                相似度阈值 <output>{threshold.toFixed(2)}</output>
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={threshold}
                aria-label="相似度阈值"
                onChange={(event) => {
                  setThreshold(Number(event.target.value));
                  invalidateCommittedSearch();
                }}
              />
            </label>
          ) : null}
          <details className="chemistry-more-options">
            <summary>更多选项</summary>
            <label>
              <span>结果上限</span>
              <select
                value={limit}
                onChange={(event) => {
                  setLimit(Number(event.target.value));
                  invalidateCommittedSearch();
                }}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
            </label>
          </details>
          <button className="primary-button chemistry-search-button" type="submit" disabled={busy || !query.trim()}>
            <Search size={17} />
            {busy ? "检索中" : "检索"}
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={!canSave}
            onClick={openSaveDialog}
            aria-label="保存结构检索"
          >
            <BookmarkPlus size={16} />
            保存检索
          </button>
        </form>
        {saveMessage ? (
          <p className="inline-feedback" role="status">
            {saveMessage}
          </p>
        ) : null}
        {error ? (
          <p className="form-error" role="alert">
            {error}
          </p>
        ) : null}
      </div>

      <div className="chemistry-results" aria-busy={busy}>
        {!result && !busy ? <EmptyState title="尚未执行结构查询" /> : null}
        {result ? (
          <>
            <header className="chemistry-result-head">
              <div>
                <strong>{result.count}</strong>
                <span>条{modeLabels[result.mode]}命中</span>
              </div>
              <dl>
                <div>
                  <dt>检索结构</dt>
                  <dd>
                    <code>{result.normalized_query}</code>
                  </dd>
                </div>
                <div>
                  <dt>查询时间</dt>
                  <dd title="本次结构查询时间，不代表来源数据的最后更新时间">{formatDate(result.as_of, true)}</dd>
                </div>
              </dl>
            </header>
            {result.items.length ? (
              <div className="chemistry-hit-list">
                {result.items.map((item) => (
                  <ChemistryHitRow key={item.id} item={item} onInspectEntity={onInspectEntity} />
                ))}
              </div>
            ) : (
              <EmptyState title="没有符合条件的结构" />
            )}
          </>
        ) : null}
      </div>
      <SavedSearchDialog
        open={saveOpen}
        domainLabel="结构"
        name={saveName}
        shared={shared}
        monitor={false}
        allowMonitor={false}
        error={saveError}
        pending={savePending}
        onNameChange={setSaveName}
        onSharedChange={setShared}
        onMonitorChange={() => undefined}
        onClose={() => setSaveOpen(false)}
        onSubmit={(event) => void saveSearch(event)}
      />
    </section>
  );
}

function ChemistryHitRow({
  item,
  onInspectEntity,
}: {
  item: ChemistrySearchHit;
  onInspectEntity: (entityId: string) => void;
}) {
  const [copied, setCopied] = useState<"smiles" | "key" | null>(null);

  async function copy(value: string, field: "smiles" | "key") {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(field);
      window.setTimeout(() => setCopied((current) => (current === field ? null : current)), 1200);
    } catch {
      setCopied(null);
    }
  }

  return (
    <article className="chemistry-hit">
      <MoleculeDepiction smiles={item.canonical_smiles} name={item.entity_name} />
      <div className="chemistry-hit-core">
        <header>
          <div>
            <h3>{item.entity_name}</h3>
            <code>{item.standard_inchi_key}</code>
          </div>
          {item.similarity !== null ? (
            <strong className="similarity-score">
              {(item.similarity * 100).toFixed(1)}
              <small>%</small>
            </strong>
          ) : null}
        </header>
        <dl className="chemistry-properties">
          <div>
            <dt>分子式</dt>
            <dd>{item.molecular_formula ?? "--"}</dd>
          </div>
          <div>
            <dt>分子量</dt>
            <dd>{number(item.molecular_weight)}</dd>
          </div>
          <div>
            <dt>精确质量</dt>
            <dd>{number(item.exact_mass)}</dd>
          </div>
          <div>
            <dt>更新时间</dt>
            <dd>{formatDate(item.updated_at)}</dd>
          </div>
        </dl>
        <div className="structure-identifiers">
          <div>
            <span>SMILES</span>
            <code>{item.canonical_smiles}</code>
            <button
              className="icon-button"
              type="button"
              title="复制 SMILES"
              aria-label={`复制 ${item.entity_name} SMILES`}
              onClick={() => void copy(item.canonical_smiles, "smiles")}
            >
              {copied === "smiles" ? <Check size={15} /> : <Copy size={15} />}
            </button>
          </div>
          <div>
            <span>InChIKey</span>
            <code>{item.standard_inchi_key}</code>
            <button
              className="icon-button"
              type="button"
              title="复制 InChIKey"
              aria-label={`复制 ${item.entity_name} InChIKey`}
              onClick={() => void copy(item.standard_inchi_key, "key")}
            >
              {copied === "key" ? <Check size={15} /> : <Copy size={15} />}
            </button>
          </div>
        </div>
        <footer>
          <button className="text-button" type="button" onClick={() => onInspectEntity(item.entity_id)}>
            查看实体 <ArrowUpRight size={14} />
          </button>
        </footer>
      </div>
    </article>
  );
}

function number(value: number | null): string {
  return value === null ? "--" : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}
