/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
import type { DataSourceReadinessCheckRead } from './DataSourceReadinessCheckRead';
import type { PublicSourceSyncRead } from './PublicSourceSyncRead';
export type DataSourceReadinessRead = {
  checks: Array<DataSourceReadinessCheckRead>;
  configuration_ready: boolean;
  connector_id: (string | null);
  cursor_present: boolean;
  delivery_channels: Array<'web' | 'mcp'>;
  freshness_age_seconds: (number | null);
  incremental: boolean;
  last_cursor_at: (string | null);
  operational_status: 'blocked' | 'disabled' | 'paused' | 'unavailable' | 'pending' | 'syncing' | 'stale' | 'ready';
  replayable: boolean;
  source_id: string;
  sync_status?: (PublicSourceSyncRead | null);
};
