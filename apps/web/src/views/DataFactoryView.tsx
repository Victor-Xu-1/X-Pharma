import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { ErrorState, Spinner } from "../components/common";
import { ApiError } from "../lib/api";
import type { DataSource, IngestionRun } from "../lib/contracts/dataFactory";
import {
  cancelIngestionRun,
  dataFactoryKeys,
  loadDataFactory,
  loadIngestionFindings,
  loadSearchProjectionStatus,
  loadSourceAssets,
  replayIngestionRun,
  triggerDataSourceScan,
  updateDataSourceState,
} from "../lib/contracts/dataFactory";
import { useLocale } from "../lib/i18n";
import { factoryText as t } from "../lib/i18n/dataFactory";
import type { User } from "../lib/types";
import { FactoryAssetsPanel } from "./dataFactory/FactoryAssetsPanel";
import { FactoryProjectionAlert } from "./dataFactory/FactoryProjectionAlert";
import { FactoryRunsPanel } from "./dataFactory/FactoryRunsPanel";
import { FactorySourcesPanel } from "./dataFactory/FactorySourcesPanel";
import { FactoryStatusStrip } from "./dataFactory/FactoryStatusStrip";
import { FindingsDrawer } from "./dataFactory/FindingsDrawer";
import { IngestionFlowOverview } from "./dataFactory/IngestionFlowOverview";
import { CancelRunDialog, ReplayRunDialog } from "./dataFactory/IngestionRunDialogs";
import { activeQuarantineStatuses, QuarantineCasesPanel } from "./dataFactory/QuarantineCasesPanel";
import { QuarantineDecisionDialog } from "./dataFactory/QuarantineDecisionDialog";
import { projectionNeedsAttention, SearchProjectionPanel } from "./dataFactory/SearchProjectionPanel";
import { SourceAssetDrawer } from "./dataFactory/SourceAssetDrawer";
import { SourceEditorDialog } from "./dataFactory/SourceEditorDialog";
import { useFactoryOperation } from "./dataFactory/useFactoryOperation";
import "./dataFactory/factory.css";

const RUNS_PER_PAGE = 25;
const ASSETS_PER_PAGE = 50;
type ReplayableRunState = "failed" | "partial" | "canceled";

export function DataFactoryView({ user }: { user: User }) {
  useLocale();
  const [selectedRun, setSelectedRun] = useState<IngestionRun | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editingSource, setEditingSource] = useState<DataSource | null>(null);
  const [replayRun, setReplayRun] = useState<IngestionRun | null>(null);
  const [cancelRun, setCancelRun] = useState<IngestionRun | null>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [selectedQuarantineVersionId, setSelectedQuarantineVersionId] = useState<string | null>(null);
  const operation = useFactoryOperation();
  const { error: actionError, busy } = operation;
  const [runPage, setRunPage] = useState(0);
  const [assetPage, setAssetPage] = useState(0);
  const projectionPanel = useRef<HTMLDetailsElement>(null);
  const snapshot = useQuery({
    queryKey: dataFactoryKeys.all,
    queryFn: ({ signal }) => loadDataFactory(signal),
  });
  const findingsQuery = useQuery({
    queryKey: dataFactoryKeys.findings(selectedRun?.id ?? "none"),
    queryFn: ({ signal }) => loadIngestionFindings(selectedRun?.id ?? "", signal),
    enabled: Boolean(selectedRun),
  });
  const assetsQuery = useQuery({
    queryKey: ["data-factory", "assets", assetPage],
    queryFn: ({ signal }) => loadSourceAssets(assetPage * ASSETS_PER_PAGE, ASSETS_PER_PAGE, signal),
  });
  const searchStatusQuery = useQuery({
    queryKey: dataFactoryKeys.searchStatus,
    queryFn: ({ signal }) => loadSearchProjectionStatus(signal),
  });
  const denied = snapshot.error instanceof ApiError && [401, 403].includes(snapshot.error.status);
  const sources = denied ? undefined : snapshot.data?.sources;
  const capabilities = snapshot.data?.capabilities;
  const datasets = snapshot.data?.datasets ?? [];
  const readiness = snapshot.data?.readiness ?? [];
  const searchStatus = searchStatusQuery.data;
  const runs = snapshot.data?.runs ?? [];
  const quarantineCases = snapshot.data?.quarantineCases ?? [];
  const quarantineNeedsAttention = quarantineCases.some((item) => activeQuarantineStatuses.has(item.quarantine_status));
  const assetsDenied = assetsQuery.error instanceof ApiError && [401, 403].includes(assetsQuery.error.status);
  const queryError = snapshot.error instanceof Error ? snapshot.error.message : "";
  const error = denied ? queryError : actionError || queryError;

  async function load() {
    operation.clear();
    void searchStatusQuery.refetch();
    await Promise.all([snapshot.refetch(), assetsQuery.refetch()]);
  }

  async function action(source: DataSource, kind: "scan" | "pause" | "resume") {
    await operation.execute(`${source.id}:${kind}`, "操作失败", async (current) => {
      if (kind === "scan") await triggerDataSourceScan(source.id);
      else await updateDataSourceState(source.id, kind === "pause" ? "paused" : "active");
      if (current()) await load();
    });
  }

  function showFindings(run: IngestionRun) {
    setSelectedRun(run);
  }

  async function replay(operationKey: string, reason: string) {
    if (!replayRun) return;
    if (!["failed", "partial", "canceled"].includes(replayRun.state)) {
      operation.reject("当前运行状态不允许重放，请刷新后重试");
      return;
    }
    await operation.execute(`run:${replayRun.id}:replay`, "入库运行重放失败", async (current) => {
      await replayIngestionRun(replayRun.id, operationKey, replayRun.state as ReplayableRunState, reason);
      if (current()) {
        setReplayRun(null);
        await load();
      }
    });
  }

  async function cancel(operationKey: string, reason: string) {
    if (!cancelRun) return;
    if (!cancelRun.cancelable || cancelRun.effective_state !== "running") {
      operation.reject("当前运行已不能取消，请刷新后重试");
      return;
    }
    await operation.execute(`run:${cancelRun.id}:cancel`, "入库运行取消失败", async (current) => {
      await cancelIngestionRun(cancelRun.id, operationKey, reason);
      if (current()) {
        setCancelRun(null);
        setSelectedRun(null);
        await load();
      }
    });
  }
  if (!sources && snapshot.isPending) return <Spinner label={t("正在连接数据工厂")} />;
  if (error && !sources) return <ErrorState message={error} retry={load} />;
  return (
    <section className="factory-layout">
      <div className="factory-main">
        {capabilities ? (
          <>
            <FactoryStatusStrip
              sources={sources ?? []}
              readiness={readiness}
              capabilities={capabilities}
              latestRun={runs[0]}
              stale={snapshot.isError}
            />

            {quarantineNeedsAttention ? (
              <QuarantineCasesPanel
                items={quarantineCases}
                role={user.role}
                stale={snapshot.isError}
                onOpen={setSelectedQuarantineVersionId}
              />
            ) : null}
          </>
        ) : null}

        {error ? (
          <div className="inline-error" role="alert">
            {error}
          </div>
        ) : null}
        {projectionNeedsAttention(searchStatus, searchStatusQuery.error) ? (
          <FactoryProjectionAlert
            onInspect={() => {
              projectionPanel.current?.scrollIntoView({ behavior: "auto", block: "center" });
              projectionPanel.current?.querySelector<HTMLElement>("summary")?.focus();
            }}
          />
        ) : null}
        <FactorySourcesPanel
          sources={sources ?? []}
          readiness={readiness}
          capabilities={capabilities}
          role={user.role}
          busy={Boolean(busy) || snapshot.isFetching || snapshot.isError}
          onCreate={() => setShowCreate(true)}
          onEdit={setEditingSource}
          onRefresh={() => void load()}
          onAction={(source, kind) => void action(source, kind)}
        />

        {capabilities ? (
          <>
            {!quarantineNeedsAttention ? (
              <QuarantineCasesPanel
                items={quarantineCases}
                role={user.role}
                stale={snapshot.isError}
                onOpen={setSelectedQuarantineVersionId}
              />
            ) : null}
            <SearchProjectionPanel
              panelRef={projectionPanel}
              data={searchStatus}
              pending={searchStatusQuery.isPending}
              error={searchStatusQuery.error instanceof Error ? searchStatusQuery.error : null}
              onRetry={() => void searchStatusQuery.refetch()}
            />
            <IngestionFlowOverview capabilities={capabilities} stale={snapshot.isError} />
          </>
        ) : null}

        <FactoryRunsPanel
          runs={runs}
          page={runPage}
          pageSize={RUNS_PER_PAGE}
          busy={Boolean(busy) || snapshot.isFetching || snapshot.isError}
          editable={user.role === "admin"}
          onPageChange={setRunPage}
          onOpen={showFindings}
          onReplay={(run) => {
            operation.clear();
            setReplayRun(run);
          }}
          onCancel={(run) => {
            operation.clear();
            setCancelRun(run);
          }}
        />

        <FactoryAssetsPanel
          data={assetsDenied ? undefined : assetsQuery.data}
          pending={assetsQuery.isPending}
          refreshing={assetsQuery.isFetching}
          error={assetsQuery.error instanceof Error ? assetsQuery.error : null}
          onRetry={() => void assetsQuery.refetch()}
          onPageChange={setAssetPage}
          onOpen={setSelectedAssetId}
        />
      </div>
      {showCreate ? (
        <SourceEditorDialog
          datasets={datasets}
          allowedFolderRoots={capabilities?.allowed_folder_roots ?? []}
          durableWorkflowsEnabled={capabilities?.durable_workflows_enabled === true}
          onClose={() => setShowCreate(false)}
          onCreated={async () => {
            setShowCreate(false);
            await load();
          }}
        />
      ) : null}
      {editingSource ? (
        <SourceEditorDialog
          datasets={datasets}
          allowedFolderRoots={capabilities?.allowed_folder_roots ?? []}
          durableWorkflowsEnabled={capabilities?.durable_workflows_enabled === true}
          source={editingSource}
          onClose={() => setEditingSource(null)}
          onCreated={async () => {
            setEditingSource(null);
            await load();
          }}
        />
      ) : null}
      {selectedRun ? (
        <FindingsDrawer
          run={selectedRun}
          findings={findingsQuery.data ?? null}
          error={findingsQuery.error instanceof Error ? findingsQuery.error : null}
          retry={() => void findingsQuery.refetch()}
          onClose={() => {
            setSelectedRun(null);
          }}
        />
      ) : null}
      {replayRun ? (
        <ReplayRunDialog
          run={replayRun}
          busy={busy === `run:${replayRun.id}:replay`}
          error={actionError}
          onClose={() => {
            if (!operation.isLocked()) {
              operation.clear();
              setReplayRun(null);
            }
          }}
          onConfirm={replay}
        />
      ) : null}
      {cancelRun ? (
        <CancelRunDialog
          run={cancelRun}
          busy={busy === `run:${cancelRun.id}:cancel`}
          error={actionError}
          onClose={() => {
            if (!operation.isLocked()) {
              operation.clear();
              setCancelRun(null);
            }
          }}
          onConfirm={cancel}
        />
      ) : null}
      {selectedAssetId ? (
        <SourceAssetDrawer
          assetId={selectedAssetId}
          canManage={user.role === "admin"}
          onClose={() => setSelectedAssetId(null)}
        />
      ) : null}
      {selectedQuarantineVersionId ? (
        <QuarantineDecisionDialog
          versionId={selectedQuarantineVersionId}
          canManage={user.role === "admin"}
          onClose={() => setSelectedQuarantineVersionId(null)}
          onDecided={load}
        />
      ) : null}
    </section>
  );
}
