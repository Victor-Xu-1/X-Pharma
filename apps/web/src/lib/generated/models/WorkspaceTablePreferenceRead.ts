/* generated using openapi-typescript-codegen -- do not edit */
/* istanbul ignore file */
/* tslint:disable */
/* eslint-disable */
export type WorkspaceTablePreferenceRead = {
  column_order?: Array<string>;
  column_visibility?: Record<string, boolean>;
  density?: 'comfortable' | 'compact';
  persisted: boolean;
  preference_key: 'clinical-trials' | 'deals' | 'entity-search' | 'epidemiology' | 'news-events' | 'patent-families' | 'pipeline' | 'regulatory-events';
  schema_version?: number;
  updated_at?: (string | null);
  version: number;
};
