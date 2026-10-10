import { useLocale } from "../lib/i18n";
import { governanceQualityText as t } from "../lib/i18n/governanceQuality";
import type { GovernanceActivity } from "../views/governance/useGovernanceActivity";
import { QualityHistory } from "./quality/QualityHistory";
import { QualityIssues } from "./quality/QualityIssues";
import { QualityOverview } from "./quality/QualityOverview";
import { QualitySourceCoverage } from "./quality/QualitySourceCoverage";
import type { QualityDraftState } from "./quality/useQualityDrafts";
import { useQualityOperations } from "./quality/useQualityOperations";

export function QualityOperationsPanel({
  activity,
  ready,
  draftState,
}: {
  activity: GovernanceActivity;
  ready: boolean;
  draftState: QualityDraftState;
}) {
  useLocale();
  const model = useQualityOperations(activity, ready, draftState);
  const error =
    model.validation ||
    (model.action.error instanceof Error ? model.action.error.message : "") ||
    (model.evaluation.error instanceof Error ? model.evaluation.error.message : "");
  return (
    <div className="quality-operations" aria-busy={model.busy}>
      <QualityOverview model={model} />
      {model.busy ? (
        <p role="status" className="quality-operation-status">
          {model.intent === "quality-action" ? t("正在提交处置") : t("正在评估")}
        </p>
      ) : model.submitted ? (
        <p role="status" className="quality-operation-status">
          {model.submitted === "action"
            ? t("处置已提交；以下状态以最新读取的记录为准。")
            : t("评估已完成；请核对最新快照和事件。")}
        </p>
      ) : null}
      {error ? (
        <p role="alert" className="form-error">
          {error}
        </p>
      ) : null}
      <QualitySourceCoverage reads={model} />
      <QualityHistory reads={model} />
      <QualityIssues model={model} />
    </div>
  );
}
