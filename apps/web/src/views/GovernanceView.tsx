import { useQuery } from "@tanstack/react-query";
import "../styles/governance.css";
import { RefreshCw } from "lucide-react";
import { useState } from "react";
import { ErrorState, Spinner } from "../components/common";
import { QualityOperationsPanel } from "../components/QualityOperationsPanel";
import { ResearchTabList } from "../components/ResearchTabList";
import { type GovernanceRunStatus, governanceKeys, loadGovernanceRuns } from "../lib/contracts/governance";
import { governanceReviewText as t } from "../lib/i18n/governanceReview";
import { FactReviewPanel } from "./governance/FactReviewPanel";
import { GovernanceRunsPanel } from "./governance/GovernanceRunsPanel";
import { governanceReadDenied } from "./governance/governanceQueryState";
import { IdentityReviewPanel } from "./governance/IdentityReviewPanel";
import { PublicationBatchPanel } from "./governance/PublicationBatchPanel";
import { useGovernanceReview } from "./governance/useGovernanceReview";

export function GovernanceView() {
  const review = useGovernanceReview();
  const { mode, queues, data, facts, identityCases, busy } = review;
  const [selectedRunId, setSelectedRunId] = useState("");
  const [runStatus, setRunStatus] = useState<GovernanceRunStatus | "all">("all");
  const [runOffset, setRunOffset] = useState(0);
  const runLimit = 30;
  const runs = useQuery({
    queryKey: governanceKeys.runs(runStatus, runLimit, runOffset),
    queryFn: ({ signal }) => loadGovernanceRuns(runStatus, runLimit, runOffset, signal),
    enabled: mode === "runs",
  });
  const runPage = governanceReadDenied(runs.error) ? undefined : runs.data;
  if (!data && !queues.error) return <Spinner label={t("正在读取数据审核队列")} />;
  if (!data && queues.error)
    return (
      <ErrorState
        message={queues.error instanceof Error ? queues.error.message : t("审核队列加载失败")}
        retry={() => void queues.refetch()}
      />
    );
  return (
    <>
      <ResearchTabList
        idPrefix="governance"
        ariaLabel={t("治理队列")}
        className="governance-tabs"
        activeTab={mode}
        onChange={review.changeMode}
        tabs={[
          {
            key: "facts",
            label: t("事实审核 {count}", { count: facts.length }),
            panelId: "governance-active-panel",
            disabled: busy,
          },
          {
            key: "identity",
            label: t("实体消歧 {count}", { count: identityCases.length }),
            panelId: "governance-active-panel",
            disabled: busy,
          },
          { key: "quality", label: t("质量运营"), panelId: "governance-active-panel", disabled: busy },
          {
            key: "runs",
            label: `${t("运行追踪")}${runPage ? ` ${runPage.total}` : ""}`,
            panelId: "governance-active-panel",
            disabled: busy,
          },
        ]}
      />
      {queues.error ? (
        <>
          <p role="status" className="field-help">
            {t("读取失败；以下为上次成功读取的记录，恢复前不能提交决策。")}
          </p>
          <ErrorState
            message={queues.error instanceof Error ? queues.error.message : t("审核队列加载失败")}
            retry={() => void queues.refetch()}
          />
        </>
      ) : null}
      {mode === "facts" || mode === "identity" ? (
        <div className="governance-review-toolbar">
          <button
            type="button"
            className="secondary-button"
            disabled={busy || queues.isFetching}
            onClick={() => void queues.refetch()}
          >
            <RefreshCw size={15} />
            {t("刷新审核队列")}
          </button>
          {review.activity.intent === "review" ? (
            <p role="status">{t("正在提交审核决策")}</p>
          ) : review.submitted ? (
            <p role="status">{t("审核决策已提交；是否可见以最新权威记录为准。")}</p>
          ) : null}
        </div>
      ) : null}
      <div role="tabpanel" id="governance-active-panel" aria-labelledby={`governance-tab-${mode}`}>
        {mode === "facts" ? (
          <>
            <fieldset className="governance-review-lock" disabled={busy}>
              <PublicationBatchPanel
                facts={facts}
                ready={review.queueReady}
                activity={review.activity}
                onQueuesChanged={() => queues.refetch()}
              />
            </fieldset>
            <FactReviewPanel review={review} />
          </>
        ) : mode === "identity" ? (
          <IdentityReviewPanel review={review} />
        ) : mode === "quality" ? (
          <QualityOperationsPanel />
        ) : (
          <GovernanceRunsPanel
            page={runPage ?? null}
            loading={!runPage && !runs.error}
            error={runs.error instanceof Error ? runs.error.message : ""}
            status={runStatus}
            offset={runOffset}
            selectedRunId={selectedRunId}
            onStatus={(value) => {
              setRunStatus(value);
              setRunOffset(0);
              setSelectedRunId("");
            }}
            onOffset={setRunOffset}
            onSelect={setSelectedRunId}
            onRetry={() => void runs.refetch()}
          />
        )}
      </div>
    </>
  );
}
