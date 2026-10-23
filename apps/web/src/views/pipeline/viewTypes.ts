import type {
  PipelineAnalysisDimension,
  PipelineAnalysisLimit,
  PipelineAnalysisStageScope,
  PipelineAnalysisView,
  PipelineResultGrain,
  PipelineSearchFilters,
  PipelineTargetAggregation,
} from "../../lib/contracts/pipeline";
export interface PipelineViewProps {
  displayMode: "list" | "landscape";
  resultGrain: PipelineResultGrain;
  analysisDimension: PipelineAnalysisDimension;
  analysisView: PipelineAnalysisView;
  analysisLimit: PipelineAnalysisLimit;
  analysisStageScope: PipelineAnalysisStageScope;
  targetAggregation: PipelineTargetAggregation;
  initialFilters: PipelineSearchFilters;
  onSearchChange: (filters: PipelineSearchFilters) => void;
  onDisplayModeChange: (mode: "list" | "landscape") => void;
  onResultGrainChange: (grain: PipelineResultGrain) => void;
  onAnalysisChange: (next: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
  onOpenDrug: (entityId: string) => void;
  onOpenEntity: (entityId: string) => void;
  onOpenTarget?: (entityId: string) => void;
  onOpenDisease?: (entityId: string) => void;
  onOpenOrganization?: (entityId: string) => void;
  onOpenTrialsForDrug: (entityId: string) => void;
  onOpenDealsForDrug: (entityId: string) => void;
}
