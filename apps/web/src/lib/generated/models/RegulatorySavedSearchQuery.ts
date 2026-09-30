/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { RegulatoryDesignationType } from './RegulatoryDesignationType';
import type { RegulatoryLabelChangeType } from './RegulatoryLabelChangeType';
import type { RegulatorySafetySeverity } from './RegulatorySafetySeverity';
import type { RegulatorySafetySignalType } from './RegulatorySafetySignalType';
import type { RegulatorySafetyStatus } from './RegulatorySafetyStatus';
export type RegulatorySavedSearchQuery = {
  agency?: (string | null);
  analysis_view?: 'chart' | 'table';
  decision_from?: (string | null);
  decision_to?: (string | null);
  designation_type?: (RegulatoryDesignationType | null);
  display_mode?: 'list' | 'landscape';
  event_type?: (string | null);
  has_boxed_warning?: (boolean | null);
  jurisdiction?: (string | null);
  label_change_type?: (RegulatoryLabelChangeType | null);
  'q'?: (string | null);
  safety_severity?: (RegulatorySafetySeverity | null);
  safety_signal_type?: (RegulatorySafetySignalType | null);
  safety_status?: (RegulatorySafetyStatus | null);
  sort?: Array<string>;
  sort_by?: 'decision_date' | 'title' | 'agency' | 'jurisdiction' | 'event_type' | 'status' | 'subject' | 'source_updated_at';
  sort_direction?: 'asc' | 'desc';
  source_updated_from?: (string | null);
  source_updated_to?: (string | null);
  status?: (string | null);
};
