import type {
  PipelineAnalysisDimension,
  PipelineAnalysisLimit,
  PipelineAnalysisStageScope,
  PipelineAnalysisView,
  PipelineTargetAggregation,
} from "../../lib/contracts/pipeline";
import type { PipelineLandscapeRead } from "../../lib/generated";
export type PipelineLandscapeFilterField =
  | "phase"
  | "globalPhase"
  | "chinaPhase"
  | "targetEntityId"
  | "targetCombinationKey"
  | "diseaseEntityId"
  | "modality"
  | "geography"
  | "organizationEntityId";

export type PipelineLandscapeEntityOpener = (entityId: string) => void;

export interface PipelineLandscapeProps {
  landscape: PipelineLandscapeRead;
  dimension: PipelineAnalysisDimension;
  view: PipelineAnalysisView;
  limit: PipelineAnalysisLimit;
  stageScope: PipelineAnalysisStageScope;
  targetAggregation: PipelineTargetAggregation;
  onFilter: (field: PipelineLandscapeFilterField, value: string, label?: string) => void;
  onOpenEntity: PipelineLandscapeEntityOpener;
  onOpenTarget?: PipelineLandscapeEntityOpener;
  onOpenDisease?: PipelineLandscapeEntityOpener;
  onOpenOrganization?: PipelineLandscapeEntityOpener;
  onAnalysisChange: (next: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
}
