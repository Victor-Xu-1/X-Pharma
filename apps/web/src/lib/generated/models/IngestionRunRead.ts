/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { IngestionRunStageRead } from './IngestionRunStageRead';
import type { RunState } from './RunState';
export type IngestionRunRead = {
  cancel_requested_at: (string | null);
  cancelable: boolean;
  completed_at: (string | null);
  completed_versions: number;
  counters: Record<string, number>;
  created_at: string;
  data_source_id: string;
  effective_state: RunState;
  error_summary: (string | null);
  heartbeat_at: (string | null);
  id: string;
  progress_percent: number;
  result: Record<string, any>;
  stages: Array<IngestionRunStageRead>;
  started_at: (string | null);
  state: RunState;
  temporal_run_id: (string | null);
  temporal_workflow_id: (string | null);
  total_versions: number;
  workflow_id: string;
};
