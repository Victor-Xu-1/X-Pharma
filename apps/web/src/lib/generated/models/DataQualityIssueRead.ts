/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type DataQualityIssueRead = {
  acknowledged_at: (string | null);
  actual_value: number;
  comparison: 'gte' | 'lte';
  created_at: string;
  description: string;
  detected_at: string;
  id: string;
  last_snapshot_id: string;
  metric_key: string;
  owner_display_name?: (string | null);
  owner_user_id: (string | null);
  resolution_notes: (string | null);
  resolved_at: (string | null);
  scope_id: (string | null);
  scope_type: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  sla_due_at: string;
  status: 'open' | 'acknowledged' | 'ready_to_resolve' | 'resolved' | 'waived';
  threshold_value: number;
  title: string;
  updated_at: string;
  version: number;
};
