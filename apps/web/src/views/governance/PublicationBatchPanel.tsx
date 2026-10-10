import { ClipboardCheck } from "lucide-react";
import { ErrorState } from "../../components/common";
import type { StagedFact } from "../../lib/contracts/governance";
import { governancePublicationText as t } from "../../lib/i18n/governancePublication";
import { ProjectionMaintenancePanel } from "./ProjectionMaintenancePanel";
import { ProjectionRebuildDialog } from "./ProjectionRebuildDialog";
import { PublicationHistory } from "./PublicationHistory";
import { PublicationPreview } from "./PublicationPreview";
import { PublicationSelection } from "./PublicationSelection";
import type { GovernanceActivity } from "./useGovernanceActivity";
import { usePublicationBatch } from "./usePublicationBatch";

export function PublicationBatchPanel({
  facts,
  ready,
  activity,
  onQueuesChanged,
}: {
  facts: StagedFact[];
  ready: boolean;
  activity: GovernanceActivity;
  onQueuesChanged: () => unknown;
}) {
  const batch = usePublicationBatch({ facts, ready, activity, onQueuesChanged });
  const maintenanceError = batch.maintenanceJobs.error instanceof Error ? batch.maintenanceJobs.error.message : "";
  return (
    <details className="publication-control">
      <summary>
        <span>
          <ClipboardCheck size={16} />
          {t("批次发布与撤回")}
        </span>
        <small>
          {batch.history
            ? batch.history.length === 1
              ? t("1 个治理批次")
              : t("{count} 个治理批次", { count: batch.history.length })
            : ""}
        </small>
      </summary>
      {batch.activity.intent.startsWith("publication:") ? (
        <p role="status" className="publication-operation-status">
          {t(
            batch.activity.intent === "publication:commit"
              ? "正在提交固定预览"
              : batch.activity.intent === "publication:maintenance"
                ? "正在提交投影维护任务"
                : "正在生成固定预览",
          )}
        </p>
      ) : batch.notice ? (
        <p role="status" className="publication-operation-status">
          {batch.notice}
        </p>
      ) : null}
      <div className="publication-control-body">
        <PublicationSelection facts={facts} batch={batch} />
        <PublicationHistory batch={batch} />
        <PublicationPreview batch={batch} />
      </div>
      {batch.maintenanceAccess.error instanceof Error ? (
        <ErrorState
          message={batch.maintenanceAccess.error.message}
          retry={() => void batch.maintenanceAccess.refetch()}
        />
      ) : null}
      {batch.allowed ? (
        <>
          <ProjectionMaintenancePanel
            jobs={batch.jobs ?? []}
            loading={batch.maintenanceJobs.isPending}
            error={maintenanceError}
            busy={batch.busy || !batch.jobsReady}
            onRequest={batch.requestMaintenance}
            onRefresh={() => void batch.refreshMaintenance()}
          />
          {batch.confirmRebuild ? (
            <ProjectionRebuildDialog
              open
              busy={batch.busy}
              error={batch.error}
              onClose={batch.closeConfirmation}
              onConfirm={batch.confirmMaintenance}
              ready={batch.jobsReady && !batch.activeJob}
            />
          ) : null}
        </>
      ) : null}
    </details>
  );
}
