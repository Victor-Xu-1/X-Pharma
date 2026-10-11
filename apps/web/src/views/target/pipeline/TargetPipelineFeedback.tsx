import { ErrorState, Spinner } from "../../../components/common";
import { KeyboardScrollRegion } from "../../../components/KeyboardScrollRegion";
import { useMessages } from "../../../lib/i18n";
import { targetPipelineMessages } from "../../../lib/i18n/targetPipeline";
import { pipelineLoadingLabel } from "./presentation";
import type { TargetPipelineState } from "./useTargetPipeline";

/** Visible query feedback without unmounting controls or substituting old result rows. */
export function TargetPipelineFeedback({
  state,
  targetName,
}: {
  state: Pick<TargetPipelineState, "result" | "filters" | "filterFacets">;
  targetName: string;
}) {
  const text = useMessages(targetPipelineMessages);
  const { result, filters, filterFacets } = state;
  if (!result.isPending && !result.error && result.data) return null;
  return (
    <KeyboardScrollRegion className="target-pipeline-feedback" ariaLabel={text("查询反馈")}>
      {result.isPending ? (
        <Spinner label={pipelineLoadingLabel(targetName, filters)} />
      ) : (
        <ErrorState
          message={result.error instanceof Error ? result.error.message : text("研发项目查询失败")}
          retry={() => void result.refetch()}
        />
      )}
      {filterFacets ? (
        <p className="muted-text">
          {result.error
            ? text("筛选选项来自上一次完成的查询；当前查询失败，请调整筛选或重试。")
            : text("筛选选项来自上一次完成的查询；当前结果仍在更新。")}
        </p>
      ) : null}
    </KeyboardScrollRegion>
  );
}
