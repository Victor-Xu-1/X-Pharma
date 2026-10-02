import type {
  PipelineAnalysisDimension,
  PipelineAnalysisLimit,
  PipelineAnalysisStageScope,
  PipelineAnalysisView,
  PipelineSearchFilters,
  PipelineTargetAggregation,
} from "../../../lib/contracts/pipeline";
import type { ProvenanceSelection } from "../../../lib/contracts/provenance";
import type { CompetitiveProgram } from "../../../lib/contracts/target";
import type { TargetEntityOpener } from "../types";

export interface TargetPipelineProps {
  targetId: string;
  targetName: string;
  fallbackItems: CompetitiveProgram[];
  initialFilters?: PipelineSearchFilters;
  onFiltersChange?: (filters: PipelineSearchFilters) => void;
  onLandscapeFilterApply?: (filters: PipelineSearchFilters, displayMode: "drug" | "program" | "landscape") => void;
  initialDisplayMode?: "drug" | "program" | "landscape";
  onDisplayModeChange?: (displayMode: "drug" | "program" | "landscape") => void;
  initialAnalysis?: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  };
  onAnalysisChange?: (analysis: {
    dimension: PipelineAnalysisDimension;
    view: PipelineAnalysisView;
    limit: PipelineAnalysisLimit;
    stageScope: PipelineAnalysisStageScope;
    targetAggregation: PipelineTargetAggregation;
  }) => void;
  onOpen: (selection: ProvenanceSelection) => void;
  onOpenEntity: TargetEntityOpener;
  onOpenComparison?: (comparisonSetId: string, entityIds: string[]) => void;
}

export type TargetPipelineOptions = Pick<
  TargetPipelineProps,
  | "targetId"
  | "initialFilters"
  | "onFiltersChange"
  | "onLandscapeFilterApply"
  | "initialDisplayMode"
  | "onDisplayModeChange"
  | "initialAnalysis"
  | "onAnalysisChange"
>;
