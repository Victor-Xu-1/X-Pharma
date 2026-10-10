import { useQuery } from "@tanstack/react-query";
import { BookmarkPlus, Code2, PencilLine, Search } from "lucide-react";
import { type FormEvent, lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";

import { Spinner } from "../components/common";
import { FormStatus } from "../components/FormStatus";
import { ResearchTabList } from "../components/ResearchTabList";
import { SavedSearchDialog } from "../components/SavedSearchDialog";
import {
  type ChemistrySearchInput,
  type ChemistrySearchMode,
  chemistryKeys,
  saveChemistrySearch,
  searchChemistry,
} from "../lib/contracts/chemistry";
import type { SavedSearchRead } from "../lib/generated";
import { useLocale } from "../lib/i18n";
import {
  type ChemistryMessageKey,
  chemistryMessages,
  chemistryModeKeys as modeLabels,
  chemistryText as t,
} from "../lib/i18n/chemistry";
import { ChemistryResults } from "./chemistry/ChemistryResults";
import { StructureEditorBoundary } from "./chemistry/StructureEditorBoundary";

type ChemistryFailure = { key: ChemistryMessageKey } | { raw: string };

const chemistrySearchErrorMessages: Record<string, ChemistryMessageKey> = {
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
      if (message) return t(message);
    } catch {
      // Fall through to the public-safe message for transport and unexpected server errors.
    }
  }
  return t("结构检索暂时不可用，请稍后重试");
}

const StructureEditor = lazy(() =>
  import("../components/StructureEditor").then((module) => ({ default: module.StructureEditor })),
);

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
  useLocale();
  const saveLock = useRef(false),
    mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const [mode, setMode] = useState<ChemistrySearchMode>("exact");
  const [inputMode, setInputMode] = useState<"draw" | "text">("draw");
  const [editorActive, setEditorActive] = useState(false);
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.7);
  const [limit, setLimit] = useState(20);
  const [validationError, setValidationError] = useState<ChemistryFailure | null>(null);
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
  const [saveError, setSaveError] = useState<ChemistryFailure | null>(null);
  const [saveMessage, setSaveMessage] = useState(false);
  const search = useQuery({
    queryKey: chemistryKeys.search(request),
    queryFn: ({ signal }) => {
      if (!request) throw new Error("结构检索参数缺失");
      return searchChemistry(request, signal);
    },
    enabled: request !== null,
  });
  const result = search.error ? undefined : search.data;
  const error = validationError
    ? "key" in validationError
      ? t(validationError.key)
      : validationError.raw
    : chemistrySearchErrorMessage(search.error);
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
    setValidationError(null);
    setSaveMessage(false);
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
    setValidationError(null);
    setSaveMessage(false);
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
    setSaveMessage(false);
    setValidationError(
      Object.hasOwn(chemistryMessages, message) ? { key: message as ChemistryMessageKey } : { raw: message },
    );
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
      setValidationError({ key: "请输入结构查询" });
      return;
    }
    setValidationError(null);
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
    setSaveMessage(false);
    onSearchCommit?.();
  }

  function openSaveDialog() {
    if (!request || !result) return;
    setSaveName(t("{mode}结构检索", { mode: t(modeLabels[request.mode]) }));
    setShared(false);
    setSaveError(null);
    setSaveMessage(false);
    setSaveOpen(true);
  }

  async function saveSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saveLock.current || !mounted.current || !request || !result || !saveName.trim()) return;
    saveLock.current = true;
    const intent = { name: saveName.trim(), input: { ...request }, shared };
    setSavePending(true);
    setSaveError(null);
    try {
      const saved = await saveChemistrySearch(intent);
      if (!mounted.current) return;
      setSaveOpen(false);
      setSaveMessage(true);
      onSavedSearch?.(saved);
    } catch (caught) {
      if (mounted.current)
        setSaveError(caught instanceof Error ? { raw: caught.message } : { key: "结构检索保存失败" });
    } finally {
      saveLock.current = false;
      if (mounted.current) setSavePending(false);
    }
  }

  return (
    <section className="chemistry-workbench">
      <div className="chemistry-query">
        <div className="chemistry-query-head">
          <fieldset className="mode-control">
            <legend>{t("检索模式")}</legend>
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
                  {t(modeLabels[item])}
                </button>
              ))}
            </div>
          </fieldset>
          <ResearchTabList
            idPrefix="chemistry-input"
            ariaLabel={t("结构输入方式")}
            className="structure-input-tabs"
            activeTab={inputMode}
            tabs={[
              {
                key: "draw",
                label: t("绘制结构"),
                icon: <PencilLine size={16} />,
                panelId: "chemistry-input-active-panel",
              },
              { key: "text", label: t("高级输入"), icon: <Code2 size={16} />, panelId: "chemistry-input-active-panel" },
            ]}
            onChange={(next) => {
              changeInputMode(next);
              if (next === "draw") setEditorActive(true);
            }}
          />
        </div>

        <div role="tabpanel" id="chemistry-input-active-panel" aria-labelledby={`chemistry-input-tab-${inputMode}`}>
          {inputMode === "draw" && !editorActive ? (
            <section className="structure-editor-gate" aria-label={t("结构画板")}>
              <PencilLine size={22} aria-hidden="true" />
              <strong>{t("结构画板尚未打开")}</strong>
              <button className="primary-button" type="button" onClick={() => setEditorActive(true)}>
                <PencilLine size={16} />
                {t("打开结构画板")}
              </button>
            </section>
          ) : inputMode === "draw" ? (
            <StructureEditorBoundary onFallback={() => changeInputMode("text")}>
              <Suspense
                fallback={
                  <div className="structure-editor-loading">
                    <Spinner label={t("正在加载结构画板")} />
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
                placeholder={t(mode === "substructure" ? "输入 SMARTS" : "输入 SMILES")}
                maxLength={20_000}
                spellCheck={false}
              />
            </label>
          )}
        </div>
        <form className="chemistry-options" onSubmit={submit}>
          {mode === "similarity" ? (
            <label className="threshold-control">
              <span>
                {t("相似度阈值")} <output>{threshold.toFixed(2)}</output>
              </span>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={threshold}
                aria-label={t("相似度阈值")}
                onChange={(event) => {
                  setThreshold(Number(event.target.value));
                  invalidateCommittedSearch();
                }}
              />
            </label>
          ) : null}
          <details className="chemistry-more-options">
            <summary>{t("更多选项")}</summary>
            <label>
              <span>{t("结果上限")}</span>
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
            {t(busy ? "检索中" : "检索")}
          </button>
          <button
            className="secondary-button"
            type="button"
            disabled={!canSave}
            onClick={openSaveDialog}
            aria-label={t("保存结构检索")}
          >
            <BookmarkPlus size={16} />
            {t("保存检索")}
          </button>
        </form>
        {saveMessage ? (
          <p className="inline-feedback" role="status">
            {t("结构检索已保存，可通过当前链接恢复")}
          </p>
        ) : null}
        <FormStatus pending={false} error={error} />
      </div>

      <ChemistryResults result={result} busy={busy} failed={Boolean(error)} onInspectEntity={onInspectEntity} />
      <SavedSearchDialog
        open={saveOpen}
        domainLabel={t("结构")}
        name={saveName}
        shared={shared}
        monitor={false}
        allowMonitor={false}
        error={saveError ? ("key" in saveError ? t(saveError.key) : saveError.raw) : ""}
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
